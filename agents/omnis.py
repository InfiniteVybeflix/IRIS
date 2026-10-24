#!/usr/bin/env python3
"""
omnis.py — OMNIS: Omniscient Mastery & Navigation Intelligence System
========================================================================
The ONE agent IRIS talks to when she needs ANY skill or capability.

OMNIS knows every skill, every agent, every tool. IRIS does not look at
folders — she calls OMNIS. OMNIS routes, executes, chains, and returns.

Codename: OMNIS
Role: Universal Skills Agent / Capability Router
Domain: all (intelligence, orchestration, productivity, security)

Usage from IRIS:
    iris.omnis.execute("web_search", {"query": "latest AI news"})
    iris.omnis.chain([{"capability": "web_search", ...}, {"capability": "chart_generation", ...}])
    iris.omnis.discover("security scan")
    iris.omnis.status()
"""

import os
import sys
import json
import time
import logging
import hashlib
import threading
import traceback
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from skills import (
    SkillRouter, SkillRegistry, BaseSkill,
    skill_router, skill_registry, CAPABILITY_MANIFEST
)

logger = logging.getLogger("OMNIS")


class OMNIS:
    """
    OMNIS — The Universal Skills Agent.
    IRIS talks to OMNIS. OMNIS talks to everything else.
    No folder browsing. No manual imports. Just OMNIS.
    """

    CODENAME = "OMNIS"
    VERSION = "9.0.0"
    MAX_CHAIN_STEPS = 25

    def __init__(self, iris_core=None):
        self._lock = threading.RLock()
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._iris_core = iris_core
        self._router = skill_router
        self._registry = skill_registry
        self._running = False
        self._execution_count = 0
        self._error_count = 0
        self._agent_cache: Dict[str, Any] = {}
        self._cron_jobs: Dict[str, Any] = {}
        self._session_state: Dict[str, Any] = {}
        self._agent_map = self._build_agent_map()
        self._keyword_map = self._build_keyword_map()
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report("OMNIS started")
            init_results = self._registry.init_all()
            logger.info(f"Skill initialization: {sum(init_results.values())}/{len(init_results)} succeeded")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            for job_id, job in list(self._cron_jobs.items()):
                if "timer" in job:
                    job["timer"].cancel()
            self._cron_jobs.clear()
            self._registry.shutdown_all()
            self._running = False
            self._report("OMNIS stopped")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME, "version": self.VERSION,
                "session_id": self._session_id, "running": self._running,
                "execution_count": self._execution_count, "error_count": self._error_count,
                "capabilities_available": len(CAPABILITY_MANIFEST),
                "skills_registered": len(self._registry.list_skills()),
                "categories": self._registry.list_categories(),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def execute(self, capability: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self._running:
            return {"success": False, "error": "OMNIS not running. Call start() first."}
        params = params or {}
        self._execution_count += 1
        try:
            result = self._router.execute(capability, params)
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"[{self.CODENAME}] Execute failed [{capability}]: {e}")
            return {"success": False, "capability": capability, "error": str(e), "traceback": traceback.format_exc()}

    def chain(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self._running:
            return {"success": False, "error": "OMNIS not running. Call start() first."}
        if len(steps) > self.MAX_CHAIN_STEPS:
            return {"success": False, "error": f"Max {self.MAX_CHAIN_STEPS} steps allowed. Got {len(steps)}."}
        self._execution_count += len(steps)
        return self._router.execute_chain(steps)

    def batch(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._running:
            return [{"success": False, "error": "OMNIS not running."}]
        self._execution_count += len(requests)
        return self._router.batch_execute(requests)

    def discover(self, query: str = None) -> List[Dict[str, Any]]:
        return self._router.discover(query)

    def smart_route(self, request: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self._running:
            return {"success": False, "error": "OMNIS not running. Call start() first."}
        request_lower = request.lower()
        context = context or {}
        best_capability = None
        best_score = 0
        best_params = {}
        for capability, info in CAPABILITY_MANIFEST.items():
            score = 0
            params = {}
            desc_words = info.get("description", "").lower().split()
            for word in desc_words:
                if len(word) > 3 and word in request_lower:
                    score += 2
            for method in info.get("methods", []):
                if method.lower() in request_lower:
                    score += 3
            cap_words = capability.replace("_", " ").lower().split()
            for word in cap_words:
                if len(word) > 2 and word in request_lower:
                    score += 4
            # Parameter extraction
            if capability == "web_search" and "search" in request_lower:
                import re
                quoted = re.search(r'"([^"]+)"', request)
                if quoted:
                    params["query"] = quoted.group(1)
                elif "search for" in request_lower:
                    params["query"] = request_lower.split("search for")[-1].strip()[:200]
                else:
                    params["query"] = request[:200]
            elif capability == "image_search_text":
                if any(k in request_lower for k in ["image", "picture", "photo"]):
                    score += 5
                    params["query"] = request
            elif capability == "code_generation":
                if any(k in request_lower for k in ["generate code", "write code", "create function", "implement"]):
                    score += 10
                    params["original_request"] = request
                    for lang in ["python", "javascript", "typescript", "java", "go", "rust", "c++", "sql", "bash"]:
                        if lang in request_lower:
                            params["language"] = lang
                            break
            elif capability == "chart_generation":
                if any(k in request_lower for k in ["chart", "graph", "plot", "visualize", "dashboard"]):
                    score += 10
            elif capability == "cybersecurity":
                if any(k in request_lower for k in ["scan", "vulnerability", "pentest", "security audit", "port scan"]):
                    score += 10
            elif capability == "academic_search":
                if any(k in request_lower for k in ["paper", "research", "arxiv", "scholar", "publication"]):
                    score += 10
            elif capability == "osint":
                if any(k in request_lower for k in ["osint", "recon", "footprint", "gather intel", "investigate"]):
                    score += 10
            elif capability == "threat_hunting":
                if any(k in request_lower for k in ["threat hunt", "ioc", "indicator", "malware"]):
                    score += 10
            elif capability == "forensics":
                if any(k in request_lower for k in ["forensics", "investigate", "artifact", "timeline", "disk"]):
                    score += 10
            elif capability == "email_report":
                if any(k in request_lower for k in ["send email", "email report", "mail", "notify"]):
                    score += 10
            if score > best_score:
                best_score = score
                best_capability = capability
                best_params = params
        if best_capability and best_score >= 3:
            logger.info(f"[OMNIS] Smart route: '{request[:50]}...' -> {best_capability} (score: {best_score})")
            merged_params = {**best_params, **context}
            return self.execute(best_capability, merged_params)
        return {"success": False, "error": f"Could not determine capability for: '{request[:100]}'", "request": request}

    def delegate(self, agent_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self._running:
            return {"success": False, "error": "OMNIS not running. Call start() first."}
        try:
            agent = self._get_agent(agent_name)
            if not agent:
                return {"success": False, "error": f"Agent '{agent_name}' not found or failed to load."}
            if hasattr(agent, 'execute'):
                result = agent.execute(task)
            elif hasattr(agent, 'handle_task'):
                result = agent.handle_task(task)
            elif hasattr(agent, 'process'):
                result = agent.process(task)
            elif hasattr(agent, 'run') and callable(getattr(agent, 'run')):
                result = agent.run(**task)
            else:
                return {"success": False, "error": f"Agent '{agent_name}' has no known execution interface."}
            return {"success": True, "agent": agent_name, "result": result, "delegated_at": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.error(f"[OMNIS] Delegate to '{agent_name}' failed: {e}")
            return {"success": False, "error": str(e), "agent": agent_name}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME, "version": self.VERSION,
                "session_id": self._session_id, "running": self._running,
                "health": self.health(), "skills": self._registry.health_all(),
                "manifest": self._router.get_manifest(),
                "execution_log": self._router.get_execution_log(10),
                "available_agents": list(self._agent_map.keys()),
                "cached_agents": list(self._agent_cache.keys()),
                "cron_jobs": len(self._cron_jobs),
                "session_state_keys": list(self._session_state.keys()),
            }

    def session_get(self, key: str, default: Any = None) -> Any:
        return self._session_state.get(key, default)

    def session_set(self, key: str, value: Any) -> None:
        self._session_state[key] = value

    def session_clear(self) -> None:
        self._session_state.clear()

    def schedule(self, job_id: str, capability: str, params: Dict[str, Any], interval_seconds: int = 60, max_runs: Optional[int] = None) -> Dict[str, Any]:
        if job_id in self._cron_jobs:
            return {"success": False, "error": f"Job '{job_id}' already exists. Cancel first."}
        def job_wrapper(run_count=[0]):
            if not self._running:
                return
            if max_runs and run_count[0] >= max_runs:
                return
            run_count[0] += 1
            try:
                self.execute(capability, params)
            except Exception as e:
                logger.error(f"[OMNIS] Scheduled job '{job_id}' error: {e}")
            if self._running and (not max_runs or run_count[0] < max_runs) and job_id in self._cron_jobs:
                timer = threading.Timer(interval_seconds, job_wrapper)
                timer.daemon = True
                timer.start()
                self._cron_jobs[job_id]["timer"] = timer
        timer = threading.Timer(interval_seconds, job_wrapper)
        timer.daemon = True
        timer.start()
        self._cron_jobs[job_id] = {
            "capability": capability, "params": params, "interval": interval_seconds,
            "max_runs": max_runs, "timer": timer, "created_at": datetime.utcnow().isoformat(),
        }
        return {"success": True, "job_id": job_id, "scheduled": True, "interval_seconds": interval_seconds, "max_runs": max_runs}

    def cancel_schedule(self, job_id: str) -> Dict[str, Any]:
        job = self._cron_jobs.pop(job_id, None)
        if job and "timer" in job:
            job["timer"].cancel()
            return {"success": True, "job_id": job_id, "cancelled": True}
        return {"success": False, "error": f"Job '{job_id}' not found."}

    def shell(self, command: str, timeout: int = 60, cwd: Optional[str] = None) -> Dict[str, Any]:
        import subprocess
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
            return {"success": result.returncode == 0, "command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def git_clone(self, repo_url: str, local_path: Optional[str] = None) -> Dict[str, Any]:
        import subprocess
        local_path = local_path or repo_url.split("/")[-1].replace(".git", "")
        result = subprocess.run(["git", "clone", "--depth", "1", repo_url, local_path], capture_output=True, text=True, timeout=120)
        return {"success": result.returncode == 0, "repo_url": repo_url, "local_path": local_path, "stdout": result.stdout, "stderr": result.stderr}

    def git_read_file(self, repo_path: str, file_path: str) -> Dict[str, Any]:
        full_path = os.path.join(repo_path, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return {"success": True, "path": file_path, "content": content, "size": len(content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def git_edit_file(self, repo_path: str, file_path: str, old_string: str, new_string: str) -> Dict[str, Any]:
        full_path = os.path.join(repo_path, file_path)
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            if old_string not in content:
                return {"success": False, "error": f"Old string not found in {file_path}"}
            new_content = content.replace(old_string, new_string, 1)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return {"success": True, "path": file_path, "old_size": len(content), "new_size": len(new_content)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_archive(self, files: List[Dict[str, Any]], archive_name: str = "deliverable.zip") -> Dict[str, Any]:
        import zipfile
        import io
        import base64
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                fpath = f.get("path", "unnamed")
                content = f.get("content", "")
                if isinstance(content, str):
                    zf.writestr(fpath, content)
                elif isinstance(content, bytes):
                    zf.writestr(fpath, content)
                else:
                    zf.writestr(fpath, json.dumps(content, indent=2))
        buffer.seek(0)
        b64 = base64.b64encode(buffer.read()).decode('utf-8')
        return {"success": True, "archive_name": archive_name, "file_count": len(files), "base64": b64}

    def generate_widget(self, widget_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        widgets = {"chart": self._widget_chart, "table": self._widget_table, "json_viewer": self._widget_json, "status_card": self._widget_status_card, "timeline": self._widget_timeline}
        generator = widgets.get(widget_type)
        if not generator:
            return {"success": False, "error": f"Unknown widget type: {widget_type}"}
        try:
            html = generator(data)
            return {"success": True, "widget_type": widget_type, "html": html, "sandboxed": True}
        except Exception as e:
            return {"success": False, "error": f"Widget generation failed: {e}"}

    def self_correct(self, capability: str, params: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
        last_error = None
        for attempt in range(1, max_retries + 1):
            result = self.execute(capability, params)
            if result.get("success"):
                if attempt > 1:
                    result["retries"] = attempt - 1
                return result
            last_error = result.get("error", "Unknown error")
            logger.warning(f"[OMNIS] Attempt {attempt}/{max_retries} failed for {capability}: {last_error}")
            if capability == "web_search" and "timeout" in str(last_error).lower():
                params["timeout"] = 30 * attempt
            time.sleep(0.5 * attempt)
        return {"success": False, "error": f"All {max_retries} attempts failed. Last: {last_error}", "capability": capability, "retries": max_retries}

    def analyze_image(self, image_data: Union[str, bytes], analysis_type: str = "general") -> Dict[str, Any]:
        return {"success": True, "analysis_type": analysis_type, "recommendation": f"Use iris.vision.analyze() for full {analysis_type} analysis."}

    def read_document(self, document_data: Union[str, bytes], doc_type: str = "auto") -> Dict[str, Any]:
        return {"success": True, "doc_type": doc_type, "recommendation": "Use specific parser modules for full extraction."}

    def _get_agent(self, agent_name: str) -> Optional[Any]:
        if agent_name in self._agent_cache:
            return self._agent_cache[agent_name]
        try:
            file_map = {
                "api_gateway": "api_gateway", "architect": "architect", "automation_forge": "automation_forge",
                "blockchain_ledger": "blockchain_ledger", "blue_sentinel": "blue_sentinel", "chart_artisan": "chart_artisan",
                "cloud_ranger": "cloud_ranger", "code_sage": "code_sage", "container_guard": "container_guard",
                "data_alchemist": "data_alchemist", "database_sage": "database_sage", "devops_maven": "devops_maven",
                "doc_scribe": "doc_scribe", "email_herald": "email_herald", "forensics_wraith": "forensics_wraith",
                "ml_engineer": "ml_engineer", "mobile_sentinel": "mobile_sentinel", "net_weaver": "net_weaver",
                "purple_judge": "purple_judge", "quantum_seer": "quantum_seer", "recon_ghost": "recon_ghost",
                "red_specter": "red_specter", "research_scholar": "research_scholar", "swarm_coordinator": "swarm_coordinator",
                "sys_overlord": "sys_overlord", "test_oracle": "test_oracle", "threat_prophet": "threat_prophet",
                "ui_visionary": "ui_visionary", "voice_herald": "voice_herald", "vuln_hunter": "vuln_hunter",
            }
            file_name = file_map.get(agent_name, agent_name)
            module = __import__(f"agents.{file_name}", fromlist=["*"])
            class_name = "".join([p.capitalize() for p in file_name.split("_")])
            if hasattr(module, class_name):
                agent = getattr(module, class_name)()
                self._agent_cache[agent_name] = agent
                return agent

            # Preferred resolution: the real agent class is a BaseAgent
            # subclass. Resolve those FIRST — the generic loop below would
            # otherwise instantiate arbitrary imported classes (e.g.
            # pathlib.Path) that happen to be sortable earlier in dir().
            try:
                from core.base_agent import BaseAgent as _BaseAgent
            except Exception:
                _BaseAgent = None
            if _BaseAgent is not None:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, _BaseAgent)
                            and attr is not _BaseAgent
                            and not getattr(attr, "__abstractmethods__", None)):
                        try:
                            agent = attr()
                            self._agent_cache[agent_name] = agent
                            return agent
                        except Exception:
                            continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and attr_name != "BaseSkill":
                    try:
                        agent = attr()
                        self._agent_cache[agent_name] = agent
                        return agent
                    except Exception:
                        continue
            return None
        except Exception as e:
            logger.error(f"[OMNIS] Failed to load agent '{agent_name}': {e}")
            return None

    def _build_agent_map(self) -> Dict[str, Dict[str, Any]]:
        return {
            "api_gateway": {"specialties": ["api", "gateway", "auth"]},
            "architect": {"specialties": ["system_design", "architecture"]},
            "automation_forge": {"specialties": ["automation", "workflows"]},
            "blockchain_ledger": {"specialties": ["blockchain", "crypto"]},
            "blue_sentinel": {"specialties": ["defense", "blue_team"]},
            "chart_artisan": {"specialties": ["charts", "visualization"]},
            "cloud_ranger": {"specialties": ["cloud", "aws", "azure", "gcp"]},
            "code_sage": {"specialties": ["code", "programming"]},
            "container_guard": {"specialties": ["docker", "kubernetes"]},
            "data_alchemist": {"specialties": ["data", "etl", "pipeline"]},
            "database_sage": {"specialties": ["database", "sql"]},
            "devops_maven": {"specialties": ["devops", "ci_cd"]},
            "doc_scribe": {"specialties": ["documentation", "writing"]},
            "email_herald": {"specialties": ["email", "notifications"]},
            "forensics_wraith": {"specialties": ["forensics", "investigation"]},
            "ml_engineer": {"specialties": ["ml", "ai"]},
            "mobile_sentinel": {"specialties": ["mobile", "android", "ios"]},
            "net_weaver": {"specialties": ["networking", "infrastructure"]},
            "purple_judge": {"specialties": ["compliance", "audit"]},
            "quantum_seer": {"specialties": ["quantum", "cryptography"]},
            "recon_ghost": {"specialties": ["reconnaissance", "osint"]},
            "red_specter": {"specialties": ["offensive", "red_team"]},
            "research_scholar": {"specialties": ["research", "academic"]},
            "swarm_coordinator": {"specialties": ["coordination", "multi_agent"]},
            "sys_overlord": {"specialties": ["system", "monitoring"]},
            "test_oracle": {"specialties": ["testing", "qa"]},
            "threat_prophet": {"specialties": ["threat_intel", "prediction"]},
            "ui_visionary": {"specialties": ["ui", "frontend"]},
            "voice_herald": {"specialties": ["voice", "audio"]},
            "vuln_hunter": {"specialties": ["vulnerabilities", "scanning"]},
        }

    def _build_keyword_map(self) -> Dict[str, List[str]]:
        return {
            "web_search": ["search", "find", "look up", "google", "query web"],
            "url_fetch": ["fetch url", "get page", "scrape url", "download page"],
            "image_search_text": ["find image", "image search", "picture of", "photo search"],
            "image_search_image": ["reverse image", "similar image", "search by image"],
            "academic_search": ["paper", "research", "arxiv", "publication", "journal"],
            "code_generation": ["generate code", "write code", "create function", "implement"],
            "code_review": ["review code", "audit code", "check code", "code quality"],
            "chart_generation": ["chart", "graph", "plot", "visualize", "dashboard"],
            "email_report": ["send email", "email report", "mail digest", "notification"],
            "cybersecurity": ["security scan", "vulnerability", "pentest", "security audit", "port scan"],
            "threat_hunting": ["threat hunt", "ioc", "indicator", "malware"],
            "forensics": ["forensics", "investigate", "artifact", "timeline"],
            "osint": ["osint", "recon", "footprint", "intelligence gathering"],
            "smart_memory": ["remember", "recall", "memory", "store information"],
            "voice_synthesis": ["speak", "say", "text to speech", "voice"],
            "consciousness": ["reflect", "think", "introspect"],
            "multi_agent": ["delegate", "multi agent", "swarm", "coordinate agents"],
            "self_healing": ["fix yourself", "self repair", "heal", "diagnose"],
            "predictive_analytics": ["predict", "forecast", "trend"],
            "documentation": ["document", "generate docs", "readme"],
            "web_scraper": ["scrape", "crawl", "extract data"],
            "system_automation": ["automate", "schedule", "cron", "workflow"],
            "calendar": ["calendar", "schedule", "event", "meeting", "appointment"],
            "notes": ["note", "write note", "memo", "notepad"],
            "reminders": ["remind", "reminder", "alert me", "dont forget"],
            "tasks": ["task", "todo", "to do", "to-do list"],
            "alarms": ["alarm", "wake me", "wake up"],
            "timer": ["timer", "countdown"],
            "stopwatch": ["stopwatch", "lap timer"],
            "habit_tracker": ["habit", "streak", "track habit"],
            "journal": ["journal", "diary", "daily log"],
            "brainstorming": ["brainstorm", "idea", "think of", "mind map"],
            "calculator": ["calculate", "math", "compute", "solve", "sum"],
            "unit_converter": ["convert", "unit", "meters to feet", "celsius to fahrenheit"],
            "currency_converter": ["currency", "exchange rate", "usd to eur", "convert money"],
            "weather": ["weather", "temperature", "forecast", "rain", "sunny"],
            "clock_worldtime": ["time", "what time", "world clock", "timezone"],
            "translation": ["translate", "translation", "in spanish", "in french"],
            "ocr": ["read text from image", "extract text", "scan document"],
            "document_reader": ["read pdf", "read document", "extract from doc"],
            "file_manager": ["file manager", "organize files", "find file"],
            "qr_scanner": ["qr code", "barcode", "scan qr"],
            "contacts": ["contact", "phone number", "address book"],
            "messaging": ["message", "sms", "text message"],
            "meeting_planner": ["plan meeting", "schedule meeting", "find time"],
            "screen_sharing": ["share screen", "present screen"],
            "music_control": ["play music", "pause music", "next song", "playlist"],
            "image_editor": ["edit image", "crop photo", "resize image", "filter image"],
            "image_generation": ["generate image", "create image", "draw picture"],
            "audio_transcription": ["transcribe audio", "audio to text"],
            "audio_editor": ["edit audio", "trim audio", "merge audio"],
            "screenshot_analysis": ["analyze screenshot", "whats in this image"],
            "screen_control": ["click on screen", "take screenshot"],
            "health_tracker": ["health", "heart rate", "blood pressure", "symptom"],
            "fitness_coach": ["workout", "exercise", "fitness", "gym"],
            "nutrition_planner": ["nutrition", "calorie", "meal plan", "diet"],
            "medication_reminders": ["medication", "pill", "take medicine"],
            "sleep_tracker": ["sleep", "track sleep", "bedtime"],
            "finance_manager": ["finance", "expense", "income", "transaction"],
            "budgeting": ["budget", "spending limit"],
            "shopping_assistant": ["shopping list", "price compare", "buy"],
        }

    def get_plugins(self) -> Dict[str, Any]:
        """Return all available plugins organized by category for / command."""
        categories = {}
        for cap_name, info in CAPABILITY_MANIFEST.items():
            cat = info.get("category", "other")
            if cat not in categories:
                categories[cat] = {"name": cat.replace("_", " ").title(), "plugins": []}
            categories[cat]["plugins"].append({
                "command": cap_name,
                "name": cap_name.replace("_", " ").title(),
                "description": info.get("description", ""),
                "methods": info.get("methods", []),
            })
        return {
            "success": True,
            "total_plugins": len(CAPABILITY_MANIFEST),
            "categories": list(categories.values()),
            "category_count": len(categories),
            "omnis_version": self.VERSION,
        }

    def route_plugin(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Route a /command to the appropriate capability."""
        params = params or {}
        command = command.lstrip("/").lower()
        capability_map = {
            "search": "web_search", "web_search": "web_search",
            "fetch": "url_fetch", "url": "url_fetch",
            "image": "image_search_text", "find_image": "image_search_text",
            "reverse_image": "image_search_image",
            "paper": "academic_search", "arxiv": "academic_search",
            "remember": "smart_memory", "recall": "smart_memory",
            "speak": "voice_synthesis", "tts": "voice_synthesis",
            "transcribe": "voice_recognition",
            "forecast": "predictive_analytics", "predict": "predictive_analytics",
            "local": "local_model",
            "docs": "documentation",
            "reflect": "consciousness",
            "delegate": "multi_agent",
            "heal": "self_healing", "diagnose": "self_healing",
            "chart": "chart_generation",
            "code": "code_generation", "generate_code": "code_generation",
            "review": "code_review",
            "email": "email_report", "mail": "email_report",
            "scrape": "web_scraper",
            "schedule": "system_automation",
            "scan": "cybersecurity", "pentest": "cybersecurity",
            "hunt": "threat_hunting",
            "forensics": "forensics",
            "osint": "osint",
            "disassemble": "reverse_engineering",
            "cloud": "cloud_security",
            "docker": "container_security",
            "blockchain": "blockchain_security",
            "honeypot": "deception_tech",
            "cyber_range": "cyber_range",
            "calendar": "calendar", "schedule_event": "calendar",
            "notes": "notes", "note": "notes",
            "remind": "reminders", "reminder": "reminders",
            "task": "tasks", "todo": "tasks",
            "alarm": "alarms",
            "timer": "timer",
            "stopwatch": "stopwatch",
            "habit": "habit_tracker",
            "journal": "journal", "diary": "journal",
            "brainstorm": "brainstorming",
            "calc": "calculator", "calculate": "calculator", "math": "calculator",
            "convert": "unit_converter",
            "currency": "currency_converter",
            "weather": "weather",
            "time": "clock_worldtime", "clock": "clock_worldtime",
            "translate": "translation",
            "ocr": "ocr",
            "read_doc": "document_reader", "read_pdf": "document_reader",
            "files": "file_manager",
            "qr": "qr_scanner",
            "contact": "contacts",
            "message": "messaging",
            "meeting": "meeting_planner",
            "share_screen": "screen_sharing",
            "music": "music_control",
            "edit_image": "image_editor",
            "generate_image": "image_generation",
            "transcribe_audio": "audio_transcription",
            "edit_audio": "audio_editor",
            "screenshot": "screenshot_analysis",
            "screen": "screen_control",
            "health": "health_tracker",
            "workout": "fitness_coach", "exercise": "fitness_coach",
            "nutrition": "nutrition_planner", "meal": "nutrition_planner",
            "medication": "medication_reminders", "pills": "medication_reminders",
            "sleep": "sleep_tracker",
            "finance": "finance_manager", "expense": "finance_manager",
            "budget": "budgeting",
            "shop": "shopping_assistant", "shopping": "shopping_assistant",
        }
        capability = capability_map.get(command, command)
        if capability in CAPABILITY_MANIFEST:
            return self.execute(capability, params)
        return {"success": False, "error": f"Unknown plugin command: /{command}. Use /plugins to list all."}

    def _report(self, message: str, level: str = "info", data: Any = None):
        payload = {"agent": self.CODENAME, "session_id": self._session_id, "timestamp": datetime.utcnow().isoformat(), "level": level, "message": message, "data": data}
        logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")
        if self._iris_core and hasattr(self._iris_core, 'message_bus'):
            try:
                self._iris_core.message_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception:
                pass

    def _widget_chart(self, data: Dict[str, Any]) -> str:
        ct = data.get("type", "bar")
        title = data.get("title", "Chart")
        labels = json.dumps(data.get("labels", []))
        values = json.dumps(data.get("values", []))
        return f"""<!DOCTYPE html><html><head><script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script></head><body><canvas id="c"></canvas><script>new Chart(document.getElementById('c').getContext('2d'),{{type:'{ct}',data:{{labels:{labels},datasets:[{{label:'{title}',data:{values}}}]}});</script></body></html>"""

    def _widget_table(self, data: Dict[str, Any]) -> str:
        rows = data.get("rows", [])
        headers = data.get("headers", [])
        hh = "".join(f"<th>{h}</th>" for h in headers)
        rh = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
        return f"<table border=\"1\" style=\"border-collapse:collapse;font-family:sans-serif\"><thead style=\"background:#333;color:#fff\"><tr>{hh}</tr></thead><tbody>{rh}</tbody></table>"

    def _widget_json(self, data: Dict[str, Any]) -> str:
        content = json.dumps(data.get("json", {}), indent=2)
        return f"<pre style=\"background:#1e1e1e;color:#d4d4d4;padding:16px;border-radius:8px;overflow:auto;font-family:monospace\">{content}</pre>"

    def _widget_status_card(self, data: Dict[str, Any]) -> str:
        status = data.get("status", "unknown")
        color = {"healthy": "#28a745", "warning": "#ffc107", "error": "#dc3545"}.get(status, "#6c757d")
        return f"<div style=\"border-left:4px solid {color};padding:12px 16px;background:#f8f9fa;border-radius:4px;font-family:sans-serif\"><strong style=\"color:{color};text-transform:uppercase\">{status}</strong><p>{data.get('message', '')}</p></div>"

    def _widget_timeline(self, data: Dict[str, Any]) -> str:
        events = data.get("events", [])
        items = "".join(f"<div style=\"margin:8px 0;padding-left:16px;border-left:2px solid #007bff\"><small style=\"color:#666\">{e.get('time','')}</small><br/><strong>{e.get('title','')}</strong><p>{e.get('description','')}</p></div>" for e in events)
        return f"<div style=\"font-family:sans-serif\">{items}</div>"


omnis = OMNIS()
__all__ = ["OMNIS", "omnis"]
