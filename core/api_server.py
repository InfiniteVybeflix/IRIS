#!/usr/bin/env python3
"""
core/api_server.py — IRIS v1.0 REST API Server
Exposes the Aevibron Agent Corps via HTTP for external integration.
"""

import os
import sys
import json
import time
from typing import Any, Dict, List, Optional

# Setup paths
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE)
sys.path.insert(0, os.path.join(_BASE, "agents"))
sys.path.insert(0, os.path.join(_BASE, "core"))

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    print("FastAPI not installed. Install with: pip install fastapi uvicorn")
    sys.exit(1)

from core.bootstrap import bootstrap_all, shutdown
from base_agent import Task, TaskPriority


# Pydantic models
class MissionRequest(BaseModel):
    request: str = Field(..., description="Natural language mission description")
    priority: str = Field("medium", description="Mission priority: critical, high, medium, low")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class TaskRequest(BaseModel):
    agent_name: str = Field(..., description="Target agent codename")
    action: str = Field(..., description="Action to execute")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    priority: str = Field("medium", description="Task priority")


class TemplateRequest(BaseModel):
    template_name: str = Field(..., description="Name of predefined template")
    params: Dict[str, Any] = Field(default_factory=dict, description="Template parameters")


# Global commander instance (initialized on startup)
commander = None
monitor = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="IRIS v1.0 API",
        description="Aevibron Agent Corps — Multi-Agent System API",
        version="7.0.0",
    )

    @app.on_event("startup")
    async def startup_event():
        global commander, monitor
        commander = bootstrap_all(data_dir="/mnt/agents/output/iris_v7/data", max_workers=10)
        try:
            from core.monitoring import SystemMonitor
            monitor = SystemMonitor(commander)
            monitor.start()
        except ImportError:
            pass

    @app.on_event("shutdown")
    async def shutdown_event():
        if monitor:
            monitor.stop()
        if commander:
            shutdown(commander)

    @app.get("/")
    async def root():
        return {
            "name": "IRIS v1.0",
            "status": "online",
            "agents": commander.registry.get_stats()["total_agents"] if commander else 0,
        }

    @app.get("/health")
    async def health():
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        health_data = commander.registry.health_check_all()
        return {
            "status": "healthy" if all(h.get("status") != "error" for h in health_data.values()) else "degraded",
            "agents": {name: {"status": h.get("status"), "load": h.get("load")} for name, h in health_data.items()},
        }

    @app.get("/agents")
    async def list_agents():
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        return {
            "agents": [
                {
                    "name": a.name,
                    "domain": a.domain,
                    "status": a.status.value,
                    "capabilities": a.capabilities,
                    "load": a.load,
                }
                for a in commander.registry.get_all()
            ]
        }

    @app.post("/missions")
    async def create_mission(req: MissionRequest, background_tasks: BackgroundTasks):
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")

        priority_map = {"critical": TaskPriority.CRITICAL, "high": TaskPriority.HIGH, "medium": TaskPriority.MEDIUM, "low": TaskPriority.LOW}

        def run_mission():
            mission = commander.receive_mission(req.request)
            # Override priority if specified
            for t in mission.tasks:
                t.priority = priority_map.get(req.priority.lower(), TaskPriority.MEDIUM)
            commander.coordinate(mission)
            report = commander.aggregate(mission)
            commander.learn(mission)
            return report

        background_tasks.add_task(run_mission)
        return {"status": "accepted", "message": "Mission queued for execution"}

    @app.get("/missions")
    async def list_missions():
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        return {"missions": commander.get_all_missions()}

    @app.get("/missions/{mission_id}")
    async def get_mission(mission_id: str):
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        status = commander.get_mission_status(mission_id)
        if not status:
            raise HTTPException(status_code=404, detail="Mission not found")
        return status

    @app.post("/tasks")
    async def execute_task(req: TaskRequest):
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")

        priority_map = {"critical": TaskPriority.CRITICAL, "high": TaskPriority.HIGH, "medium": TaskPriority.MEDIUM, "low": TaskPriority.LOW}

        task = Task(
            agent_name=req.agent_name,
            description=f"Direct task: {req.action}",
            priority=priority_map.get(req.priority.lower(), TaskPriority.MEDIUM),
            payload={"action": req.action, **req.payload},
        )

        result = commander.assign(task)
        if not result:
            raise HTTPException(status_code=500, detail="Task assignment failed")
        return result.to_dict()

    @app.get("/templates")
    async def list_templates():
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        try:
            from core.commander_extensions import patch_commander
            patch_commander()
            return {"templates": commander.get_template_list()}
        except Exception as e:
            return {"templates": [], "error": str(e)}

    @app.post("/templates/{template_name}")
    async def execute_template(template_name: str, req: TemplateRequest):
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        try:
            from core.commander_extensions import patch_commander
            patch_commander()
            report = commander.execute_template(template_name, req.params)
            return report.to_dict()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/memory")
    async def get_memory(key: Optional[str] = None, mission_id: str = "global"):
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        if key:
            val = commander.shared_memory.retrieve(key, mission_id=mission_id)
            return {"key": key, "value": val}
        return {"keys": commander.shared_memory.list_keys(mission_id=mission_id)}

    @app.get("/monitor")
    async def get_monitor():
        if not monitor:
            return {"status": "monitoring not available"}
        return monitor.get_dashboard()

    @app.get("/bus/stats")
    async def bus_stats():
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        return commander.message_bus.get_stats()

    @app.get("/queue/stats")
    async def queue_stats():
        if not commander:
            raise HTTPException(status_code=503, detail="Commander not initialized")
        return commander.task_queue.get_stats()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
