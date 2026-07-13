"""
IRIS Skills Framework — Unified Capability Router
==================================================
All skills organized into 4 domains:
  intelligence  — Research, memory, voice, predictive analytics, documentation
  orchestration — Consciousness, multi-agent coordination, self-healing
  productivity  — Charts, code generation, email, web scraping, system automation
  security      — Cybersecurity, forensics, OSINT, threat hunting, cloud/container/blockchain security

Exports:
  SkillRouter   — Route any capability request to the correct skill handler
  BaseSkill     — Abstract base class all skills extend
  SkillRegistry — Central registry of all available skills
  CAPABILITY_MANIFEST — All 60+ capability definitions
"""

import os
import sys
import json
import logging
import importlib
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

CAPABILITY_MANIFEST = {
    "web_search": {
        "category": "intelligence",
        "skill": "research_engine",
        "description": "Web search with multi-query support and result parsing",
        "methods": ["search", "multi_search", "parse_results"],
    },
    "url_fetch": {
        "category": "intelligence",
        "skill": "research_engine",
        "description": "URL content extraction with parallel loading",
        "methods": ["fetch", "fetch_parallel", "extract_text", "extract_links"],
    },
    "image_search_text": {
        "category": "intelligence",
        "skill": "research_engine",
        "description": "Text-to-image search across providers",
        "methods": ["search_by_text"],
    },
    "image_search_image": {
        "category": "intelligence",
        "skill": "research_engine",
        "description": "Image-to-image reverse image search",
        "methods": ["search_by_image"],
    },
    "academic_search": {
        "category": "intelligence",
        "skill": "research_engine",
        "description": "Academic paper search via arXiv, Scholar APIs",
        "methods": ["arxiv_search", "scholar_search", "literature_review"],
    },
    "smart_memory": {
        "category": "intelligence",
        "skill": "smart_memory",
        "description": "Semantic memory storage, retrieval, and consolidation",
        "methods": ["store", "retrieve", "search", "consolidate", "forget"],
    },
    "voice_synthesis": {
        "category": "intelligence",
        "skill": "voice_system",
        "description": "Text-to-speech with multiple voice options",
        "methods": ["synthesize", "list_voices"],
    },
    "voice_recognition": {
        "category": "intelligence",
        "skill": "voice_system",
        "description": "Speech-to-text transcription",
        "methods": ["transcribe", "detect_language"],
    },
    "predictive_analytics": {
        "category": "intelligence",
        "skill": "predictive_intel",
        "description": "Trend prediction and forecasting",
        "methods": ["forecast", "trend_analysis", "anomaly_detect"],
    },
    "local_model": {
        "category": "intelligence",
        "skill": "local_model",
        "description": "Local LLM inference without external APIs",
        "methods": ["generate", "embed", "classify"],
    },
    "documentation": {
        "category": "intelligence",
        "skill": "documentation",
        "description": "Auto-generate docs from code, APIs, or specs",
        "methods": ["generate_api_docs", "generate_readme", "generate_wiki"],
    },
    "consciousness": {
        "category": "orchestration",
        "skill": "consciousness",
        "description": "Cognitive awareness, emotional state, reflection",
        "methods": ["reflect", "emote", "perceive", "introspect"],
    },
    "multi_agent": {
        "category": "orchestration",
        "skill": "multi_agent",
        "description": "Multi-agent swarm coordination and task delegation",
        "methods": ["delegate", "coordinate", "aggregate", "assign"],
    },
    "self_healing": {
        "category": "orchestration",
        "skill": "self_healing",
        "description": "Self-diagnostics, auto-repair, fault recovery",
        "methods": ["diagnose", "repair", "rollback", "health_check"],
    },
    "chart_generation": {
        "category": "productivity",
        "skill": "chart_manager",
        "description": "Generate charts: bar, line, pie, scatter, heatmap",
        "methods": ["create_chart", "create_dashboard", "export_png"],
    },
    "code_generation": {
        "category": "productivity",
        "skill": "code_engine",
        "description": "Generate code in any language from natural language",
        "methods": ["generate", "complete", "explain", "translate"],
    },
    "code_review": {
        "category": "productivity",
        "skill": "code_engine",
        "description": "Security audit, style check, refactoring suggestions",
        "methods": ["review", "audit_security", "suggest_refactor", "find_bugs"],
    },
    "email_report": {
        "category": "productivity",
        "skill": "email_reporter",
        "description": "Send formatted emails, reports, digests",
        "methods": ["send_email", "send_digest", "send_alert"],
    },
    "web_scraper": {
        "category": "productivity",
        "skill": "web_scraper",
        "description": "Structured data extraction from websites",
        "methods": ["scrape", "crawl", "extract_table", "monitor_changes"],
    },
    "system_automation": {
        "category": "productivity",
        "skill": "system_automation",
        "description": "File ops, scheduled tasks, workflow automation",
        "methods": ["schedule_task", "watch_file", "automate_workflow"],
    },
    "cybersecurity": {
        "category": "security",
        "skill": "cyber_security",
        "description": "Vulnerability scanning, penetration testing, hardening",
        "methods": ["scan_vulns", "pentest", "harden", "scan_ports"],
    },
    "threat_hunting": {
        "category": "security",
        "skill": "threat_hunter",
        "description": "IOC search, behavioral analysis, threat detection",
        "methods": ["hunt_iocs", "behavioral_analysis", "detect_threats"],
    },
    "forensics": {
        "category": "security",
        "skill": "forensics",
        "description": "Digital forensics, artifact analysis, timeline reconstruction",
        "methods": ["analyze_disk", "reconstruct_timeline", "extract_artifacts"],
    },
    "osint": {
        "category": "security",
        "skill": "osint",
        "description": "Open-source intelligence gathering and correlation",
        "methods": ["gather", "correlate", "enrich", "footprint"],
    },
    "reverse_engineering": {
        "category": "security",
        "skill": "reverse_engineering",
        "description": "Binary analysis, disassembly, decompilation",
        "methods": ["disassemble", "decompile", "analyze_binary"],
    },
    "cloud_security": {
        "category": "security",
        "skill": "cloud_security",
        "description": "Cloud config audit, IAM review, compliance check",
        "methods": ["audit_config", "review_iam", "check_compliance"],
    },
    "container_security": {
        "category": "security",
        "skill": "container_security",
        "description": "Docker/K8s security scanning and hardening",
        "methods": ["scan_image", "audit_k8s", "check_dockerfile"],
    },
    "blockchain_security": {
        "category": "security",
        "skill": "blockchain_security",
        "description": "Smart contract audit, transaction analysis",
        "methods": ["audit_contract", "analyze_transactions"],
    },
    "deception_tech": {
        "category": "security",
        "skill": "deception_tech",
        "description": "Honeypot deployment, deception strategy",
        "methods": ["deploy_honeypot", "generate_deception"],
    },
    "cyber_range": {
        "category": "security",
        "skill": "cyber_range",
        "description": "Cyber range scenario creation and execution",
        "methods": ["create_scenario", "run_exercise"],
    },
    # ─── Personal Productivity ───────────────────────────────────────────
    "calendar": {
        "category": "personal_productivity",
        "skill": "calendar",
        "description": "Event scheduling, meeting planning, availability checking",
        "methods": ["create_event", "list_events", "delete_event", "check_availability", "schedule_meeting", "find_free_slots"],
    },
    "notes": {
        "category": "personal_productivity",
        "skill": "notes",
        "description": "Note-taking with full-text search, tags, folders, markdown",
        "methods": ["create", "read", "update", "delete", "search", "list"],
    },
    "reminders": {
        "category": "personal_productivity",
        "skill": "reminders",
        "description": "Time-based and recurring reminders with snooze",
        "methods": ["set", "list", "cancel", "snooze"],
    },
    "tasks": {
        "category": "personal_productivity",
        "skill": "tasks",
        "description": "To-do lists, task management, prioritization",
        "methods": ["create", "list", "complete", "delete", "prioritize"],
    },
    "alarms": {
        "category": "personal_productivity",
        "skill": "alarms",
        "description": "One-time and recurring alarms with labels",
        "methods": ["set", "list", "cancel"],
    },
    "timer": {
        "category": "personal_productivity",
        "skill": "timer",
        "description": "Countdown timer with multiple named timers",
        "methods": ["start", "status", "cancel"],
    },
    "stopwatch": {
        "category": "personal_productivity",
        "skill": "stopwatch",
        "description": "Lap timing and split tracking",
        "methods": ["start", "lap", "stop", "status"],
    },
    "habit_tracker": {
        "category": "personal_productivity",
        "skill": "habit_tracker",
        "description": "Track habits, streaks, and progress",
        "methods": ["create", "log", "status", "list"],
    },
    "journal": {
        "category": "personal_productivity",
        "skill": "journal",
        "description": "Daily journaling with prompts and search",
        "methods": ["write", "read", "search", "prompt"],
    },
    "brainstorming": {
        "category": "personal_productivity",
        "skill": "brainstorming",
        "description": "Idea generation, mind mapping, concept expansion",
        "methods": ["generate_ideas", "expand_concept", "mind_map"],
    },
    # ─── Utilities ───────────────────────────────────────────────────────
    "calculator": {
        "category": "utilities",
        "skill": "calculator",
        "description": "Basic and scientific calculations, expression evaluation",
        "methods": ["evaluate", "scientific"],
    },
    "unit_converter": {
        "category": "utilities",
        "skill": "unit_converter",
        "description": "Convert between units of measurement (length, weight, temp, volume, speed, data, time, area)",
        "methods": ["convert", "list_units"],
    },
    "currency_converter": {
        "category": "utilities",
        "skill": "currency_converter",
        "description": "Real-time currency conversion with live rates",
        "methods": ["convert", "list_currencies"],
    },
    "weather": {
        "category": "utilities",
        "skill": "weather",
        "description": "Current weather, forecasts, weather alerts",
        "methods": ["current", "forecast"],
    },
    "clock_worldtime": {
        "category": "utilities",
        "skill": "clock_worldtime",
        "description": "Current time, world clocks, time zone conversion",
        "methods": ["now", "world_clock", "convert"],
    },
    "translation": {
        "category": "utilities",
        "skill": "translation",
        "description": "Text translation between 17+ languages",
        "methods": ["translate", "detect", "list_languages"],
    },
    "ocr": {
        "category": "utilities",
        "skill": "ocr",
        "description": "Extract text from images using pytesseract",
        "methods": ["extract"],
    },
    "document_reader": {
        "category": "utilities",
        "skill": "document_reader",
        "description": "Read PDF, DOCX, TXT, and other document formats",
        "methods": ["read", "metadata"],
    },
    "file_manager": {
        "category": "utilities",
        "skill": "file_manager",
        "description": "File operations, search, copy, move, delete, organize",
        "methods": ["list", "copy", "move", "delete", "search", "info"],
    },
    "qr_scanner": {
        "category": "utilities",
        "skill": "qr_scanner",
        "description": "Generate and read QR codes and barcodes",
        "methods": ["generate", "read"],
    },
    # ─── Communication ───────────────────────────────────────────────────
    "contacts": {
        "category": "communication",
        "skill": "contacts",
        "description": "Contact management, search, groups",
        "methods": ["add", "search", "get", "delete", "list"],
    },
    "messaging": {
        "category": "communication",
        "skill": "messaging",
        "description": "Unified messaging hub for SMS, email, chat",
        "methods": ["send", "history"],
    },
    "meeting_planner": {
        "category": "communication",
        "skill": "meeting_planner",
        "description": "Coordinate meetings across time zones",
        "methods": ["find_slot", "convert_time"],
    },
    "screen_sharing": {
        "category": "communication",
        "skill": "screen_sharing",
        "description": "Screen sharing session control",
        "methods": ["start", "stop", "status"],
    },
    # ─── Media ───────────────────────────────────────────────────────────
    "music_control": {
        "category": "media",
        "skill": "music_control",
        "description": "Music playback control, playlists, queue",
        "methods": ["play", "pause", "next", "previous", "volume", "queue", "playlist"],
    },
    "image_editor": {
        "category": "media",
        "skill": "image_editor",
        "description": "Image editing: crop, resize, filters, info",
        "methods": ["resize", "crop", "filter", "info"],
    },
    "image_generation": {
        "category": "media",
        "skill": "image_generation",
        "description": "Generate images from text prompts",
        "methods": ["generate"],
    },
    "audio_transcription": {
        "category": "media",
        "skill": "audio_transcription",
        "description": "Transcribe audio to text using Whisper",
        "methods": ["transcribe"],
    },
    "audio_editor": {
        "category": "media",
        "skill": "audio_editor",
        "description": "Audio trim, merge, format conversion",
        "methods": ["trim", "merge", "convert"],
    },
    "screenshot_analysis": {
        "category": "media",
        "skill": "screenshot_analysis",
        "description": "Analyze screenshots for content detection",
        "methods": ["analyze"],
    },
    "screen_control": {
        "category": "media",
        "skill": "screen_control",
        "description": "Remote screen control and automation",
        "methods": ["click", "type", "screenshot"],
    },
    # ─── Health & Fitness ────────────────────────────────────────────────
    "health_tracker": {
        "category": "health_fitness",
        "skill": "health_tracker",
        "description": "Track vitals, symptoms, and health metrics",
        "methods": ["log", "history", "trends"],
    },
    "fitness_coach": {
        "category": "health_fitness",
        "skill": "fitness_coach",
        "description": "Workout plans, exercise tracking, progress",
        "methods": ["get_plan", "log_workout", "progress"],
    },
    "nutrition_planner": {
        "category": "health_fitness",
        "skill": "nutrition_planner",
        "description": "Meal planning, calorie tracking, recipes",
        "methods": ["log_meal", "lookup", "daily_summary", "plan_meals"],
    },
    "medication_reminders": {
        "category": "health_fitness",
        "skill": "medication_reminders",
        "description": "Track medications, doses, schedules",
        "methods": ["add", "log_dose", "schedule", "list"],
    },
    "sleep_tracker": {
        "category": "health_fitness",
        "skill": "sleep_tracker",
        "description": "Track sleep duration, quality, patterns",
        "methods": ["log", "stats"],
    },
    # ─── Finance ─────────────────────────────────────────────────────────
    "finance_manager": {
        "category": "finance",
        "skill": "finance_manager",
        "description": "Income, expenses, accounts tracking",
        "methods": ["add_transaction", "summary", "report"],
    },
    "budgeting": {
        "category": "finance",
        "skill": "budgeting",
        "description": "Budget creation, tracking, alerts",
        "methods": ["create_budget", "log_spending", "check_budget"],
    },
    "shopping_assistant": {
        "category": "finance",
        "skill": "shopping_assistant",
        "description": "Price comparison, shopping lists, deals",
        "methods": ["create_list", "add_item", "compare_prices", "get_list"],
    },
}


class BaseSkill(ABC):
    """Every skill in IRIS extends BaseSkill."""

    def __init__(self, name: str, category: str, capabilities: List[str]):
        self.name = name
        self.category = category
        self.capabilities = capabilities
        self._initialized = False
        self._metadata: Dict[str, Any] = {}
        self._created_at = datetime.utcnow().isoformat()

    @abstractmethod
    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

    def health(self) -> Dict[str, Any]:
        return {
            "skill": self.name,
            "category": self.category,
            "initialized": self._initialized,
            "capabilities": self.capabilities,
            "created_at": self._created_at,
        }

    def init(self) -> bool:
        self._initialized = True
        return True

    def shutdown(self) -> bool:
        self._initialized = False
        return True

    def list_capabilities(self) -> List[str]:
        return list(self.capabilities)

    def can_handle(self, capability: str) -> bool:
        return capability in self.capabilities


class SkillRegistry:
    """Central registry for all skills. Skills self-register on import."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills: Dict[str, BaseSkill] = {}
            cls._instance._category_index: Dict[str, List[str]] = defaultdict(list)
            cls._instance._capability_index: Dict[str, str] = {}
            cls._instance._initialized = False
        return cls._instance

    def register(self, skill: BaseSkill) -> None:
        if skill.name in self._skills:
            logger.warning(f"Skill '{skill.name}' already registered. Overwriting.")
        self._skills[skill.name] = skill
        self._category_index[skill.category].append(skill.name)
        for cap in skill.capabilities:
            self._capability_index[cap] = skill.name
        logger.info(f"Skill registered: {skill.name} ({skill.category}) with {len(skill.capabilities)} capabilities")

    def get(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def get_by_capability(self, capability: str) -> Optional[BaseSkill]:
        skill_name = self._capability_index.get(capability)
        if skill_name:
            return self._skills.get(skill_name)
        return None

    def list_skills(self, category: Optional[str] = None) -> List[str]:
        if category:
            return list(self._category_index.get(category, []))
        return list(self._skills.keys())

    def list_capabilities(self) -> List[str]:
        return list(self._capability_index.keys())

    def list_categories(self) -> List[str]:
        return list(self._category_index.keys())

    def health_all(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self._skills),
            "total_capabilities": len(self._capability_index),
            "categories": {cat: len(skills) for cat, skills in self._category_index.items()},
            "skills": {name: skill.health() for name, skill in self._skills.items()},
        }

    def init_all(self) -> Dict[str, bool]:
        results = {}
        for name, skill in self._skills.items():
            try:
                results[name] = skill.init()
            except Exception as e:
                logger.error(f"Failed to init skill '{name}': {e}")
                results[name] = False
        self._initialized = True
        return results

    def shutdown_all(self) -> Dict[str, bool]:
        results = {}
        for name, skill in self._skills.items():
            try:
                results[name] = skill.shutdown()
            except Exception as e:
                logger.error(f"Failed to shutdown skill '{name}': {e}")
                results[name] = False
        self._initialized = False
        return results

    def get_manifest(self) -> Dict[str, Any]:
        return {
            "manifest": CAPABILITY_MANIFEST,
            "registered_skills": self.list_skills(),
            "registered_capabilities": self.list_capabilities(),
            "categories": self.list_categories(),
            "capability_count": len(CAPABILITY_MANIFEST),
            "skill_count": len(self._skills),
        }


class SkillRouter:
    """The main entry point for all skill execution."""

    def __init__(self):
        self.registry = SkillRegistry()
        self._execution_log: List[Dict[str, Any]] = []
        self._max_log_entries = 1000

    def execute(self, capability: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        params = params or {}
        start_time = datetime.utcnow()
        try:
            skill = self.registry.get_by_capability(capability)
            if not skill:
                manifest_entry = CAPABILITY_MANIFEST.get(capability)
                if manifest_entry:
                    loaded = self._auto_load_skill(manifest_entry["category"], manifest_entry["skill"])
                    if loaded:
                        skill = self.registry.get_by_capability(capability)
                if not skill:
                    return {"success": False, "capability": capability, "error": f"No skill found for capability: {capability}", "executed_at": datetime.utcnow().isoformat()}
            result = skill.execute(capability, params)
            self._log_execution(capability, skill.name, "success", start_time)
            return {"success": True, "capability": capability, "skill": skill.name, "result": result, "executed_at": datetime.utcnow().isoformat()}
        except Exception as e:
            logger.error(f"Skill execution failed [{capability}]: {e}")
            self._log_execution(capability, None, "error", start_time, str(e))
            return {"success": False, "capability": capability, "error": str(e), "traceback": traceback.format_exc(), "executed_at": datetime.utcnow().isoformat()}

    def execute_chain(self, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(steps) > 25:
            return {"success": False, "error": "Max 25 steps allowed per chain"}
        results = []
        context = {}
        for i, step in enumerate(steps):
            capability = step.get("capability")
            params = self._inject_context(step.get("params", {}), context)
            result = self.execute(capability, params)
            results.append({"step": i, "capability": capability, "success": result.get("success", False), "result": result})
            context[f"step_{i}"] = result
            if not result.get("success") and step.get("stop_on_error", True):
                break
        return {"success": all(r["success"] for r in results), "steps_executed": len(results), "results": results}

    def batch_execute(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.execute(req["capability"], req.get("params", {})) for req in requests]

    def _auto_load_skill(self, category: str, skill_name: str) -> bool:
        try:
            module_path = f"skills.{category}.{skill_name}.skill"
            module = importlib.import_module(module_path)
            class_name = "".join([p.capitalize() for p in skill_name.split("_")]) + "Skill"
            if hasattr(module, class_name):
                skill_class = getattr(module, class_name)
                instance = skill_class()
                self.registry.register(instance)
                return True
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                    instance = attr()
                    self.registry.register(instance)
                    return True
            return False
        except Exception as e:
            logger.warning(f"Auto-load failed for {category}.{skill_name}: {e}")
            return False

    def _inject_context(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        injected = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                ref = value[2:-2].strip()
                parts = ref.split(".")
                ctx = context
                for part in parts:
                    if isinstance(ctx, dict):
                        ctx = ctx.get(part, {})
                    else:
                        ctx = {}
                injected[key] = ctx
            else:
                injected[key] = value
        return injected

    def _log_execution(self, capability: str, skill_name: Optional[str], status: str, start_time: datetime, error: str = None):
        entry = {"capability": capability, "skill": skill_name, "status": status, "started_at": start_time.isoformat(), "completed_at": datetime.utcnow().isoformat()}
        if error:
            entry["error"] = error
        self._execution_log.append(entry)
        if len(self._execution_log) > self._max_log_entries:
            self._execution_log = self._execution_log[-self._max_log_entries:]

    def get_execution_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._execution_log[-limit:]

    def get_manifest(self) -> Dict[str, Any]:
        return self.registry.get_manifest()

    def discover(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        if not query:
            return [{"name": k, **v} for k, v in CAPABILITY_MANIFEST.items()]
        query_lower = query.lower()
        matches = []
        for cap_name, info in CAPABILITY_MANIFEST.items():
            if (query_lower in cap_name.lower() or query_lower in info.get("description", "").lower() or any(query_lower in m.lower() for m in info.get("methods", []))):
                matches.append({"name": cap_name, **info})
        return matches


skill_registry = SkillRegistry()
skill_router = SkillRouter()

__all__ = ["BaseSkill", "SkillRegistry", "SkillRouter", "skill_registry", "skill_router", "CAPABILITY_MANIFEST"]
