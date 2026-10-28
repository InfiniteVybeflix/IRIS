"""IRIS Universal Agent Adapter — every agent works, none are closed.

Problem this solves:
  The corps has two generations of agents:
    - BaseAgent subclasses (vuln_hunter/SCAR, red_specter, recon_ghost, ...)
      expose `execute(Task)`.
    - Legacy commander-style classes (PORTAL, chart_artisan, cloud_ranger, ...)
      expose `start/stop/health` plus dozens of domain methods
      (scan_ports, generate_chart, audit_bucket, ...) but NO execute().

  The old delegate path only recognized execute/handle_task/process/run, so
  ~20 agents showed up as "not delegatable" — the "closed agents" bug.

This adapter runs ANY agent for real:
  1. BaseAgent subclass        → Task() → agent.execute(task)
  2. execute/handle_task/process → called directly with the payload
  3. Legacy class              → keyword dispatch: match the task text against
     the agent's public callable methods (scan_ports, generate_chart, ...)
     and invoke the best match with arguments extracted from the task.
  4. Nothing matched           → run health() + list the agent's real
     capabilities and return them honestly (never a fake result).
"""
from __future__ import annotations

import inspect
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# module file name → agent id (mirrors agents/omnis.py)
AGENT_FILES = {
    "api_gateway": "api_gateway", "architect": "architect", "automation_forge": "automation_forge",
    "blockchain_ledger": "blockchain_ledger", "blue_sentinel": "blue_sentinel",
    "chart_artisan": "chart_artisan", "cloud_ranger": "cloud_ranger", "code_sage": "code_sage",
    "container_guard": "container_guard", "data_alchemist": "data_alchemist",
    "database_sage": "database_sage", "devops_maven": "devops_maven", "doc_scribe": "doc_scribe",
    "email_herald": "email_herald", "forensics_wraith": "forensics_wraith",
    "ml_engineer": "ml_engineer", "mobile_sentinel": "mobile_sentinel", "net_weaver": "net_weaver",
    "purple_judge": "purple_judge", "quantum_seer": "quantum_seer", "recon_ghost": "recon_ghost",
    "red_specter": "red_specter", "research_scholar": "research_scholar",
    "swarm_coordinator": "swarm_coordinator", "sys_overlord": "sys_overlord",
    "test_oracle": "test_oracle", "threat_prophet": "threat_prophet",
    "ui_visionary": "ui_visionary", "voice_herald": "voice_herald", "vuln_hunter": "vuln_hunter",
}

# Methods that are infrastructure, never task handlers.
_SKIP_METHODS = {
    "start", "stop", "health", "health_check", "__init__", "execute", "handle_task",
    "process", "run", "shutdown", "restart", "main", "cli", "report", "learn",
    "set_commander", "set_message_bus", "delegate", "can_handle", "get_experience",
    "_report_to_commander", "_store_memory", "_execute_shell", "_report",
}

# Words in a task that map to method-name fragments.
_KEYWORD_HINTS = {
    "scan": "scan", "port": "port", "vulnerab": "vuln", "exploit": "exploit",
    "chart": "chart", "graph": "chart", "plot": "plot", "visual": "visual",
    "deploy": "deploy", "audit": "audit", "analy": "analy", "check": "check",
    "monitor": "monitor", "generate": "generate", "create": "create",
    "review": "review", "optimize": "optimi", "predict": "predict",
    "forecast": "predict", "test": "test", "search": "search", "find": "search",
    "fetch": "fetch", "send": "send", "email": "email", "sms": "sms",
    "message": "message", "translate": "translat", "convert": "convert",
    "backup": "backup", "restore": "restore", "log": "log", "report": "report",
    "summar": "summar", "document": "doc", "write": "write", "design": "design",
    "architect": "architect", "plan": "plan", "estimate": "estimate",
    "network": "network", "dns": "dns", "whois": "whois", "ssl": "ssl",
    "tls": "tls", "certificate": "cert", "firewall": "firewall",
    "container": "container", "docker": "docker", "kubernetes": "kube",
    "cluster": "cluster", "database": "database", "sql": "sql", "query": "query",
    "schema": "schema", "migrate": "migrate", "cloud": "cloud", "aws": "aws",
    "azure": "azure", "gcp": "gcp", "pipeline": "pipeline", "ci": "ci",
    "build": "build", "train": "train", "model": "model", "dataset": "dataset",
    "clean": "clean", "parse": "parse", "extract": "extract",
}

_agent_cache: Dict[str, Any] = {}


def load_agent(agent_name: str) -> Optional[Any]:
    """Import and instantiate an agent by id. Cached per process."""
    if agent_name in _agent_cache:
        return _agent_cache[agent_name]
    file_name = AGENT_FILES.get(agent_name, agent_name)
    try:
        module = __import__(f"agents.{file_name}", fromlist=["*"])
    except Exception as e:
        logger.error("[adapter] import agents.%s failed: %s", file_name, e)
        return None

    # Prefer BaseAgent subclasses (the real corps classes).
    try:
        from core.base_agent import BaseAgent
    except Exception:
        BaseAgent = None  # type: ignore

    candidates: List[type] = []
    if BaseAgent is not None:
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and issubclass(attr, BaseAgent)
                    and attr is not BaseAgent
                    and not getattr(attr, "__abstractmethods__", None)):
                candidates.append(attr)
    if not candidates:
        # Legacy: first concrete class defined in this module with a CODENAME
        # or a name matching the file.
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and attr.__module__ == f"agents.{file_name}"
                    and not inspect.isabstract(attr)):
                candidates.append(attr)

    for cls in candidates:
        try:
            inst = cls()
            _auto_start(inst)
            _agent_cache[agent_name] = inst
            return inst
        except Exception:
            continue
    # Last resort: any instantiable class (commander-bus arg)
    for cls in candidates:
        try:
            inst = cls(None)
            _auto_start(inst)
            _agent_cache[agent_name] = inst
            return inst
        except Exception:
            continue
    logger.error("[adapter] no loadable class in agents.%s", file_name)
    return None


def _auto_start(agent: Any) -> None:
    """Legacy commander-style agents refuse work until start() is called —
    start them automatically (best-effort, never fatal)."""
    start = getattr(agent, "start", None)
    if callable(start):
        try:
            if start():
                return
        except Exception as e:
            logger.debug("[adapter] auto-start soft-failed: %s", e)
    # Some agents expose _running directly
    if getattr(agent, "_running", True) is False:
        try:
            agent._running = True
        except Exception:
            pass


def _extract_target(task_text: str) -> str:
    """Pull a URL / domain / IP out of the task text."""
    m = re.search(r"https?://[^\s'\"<>]+", task_text)
    if m:
        return m.group(0).rstrip(".,;:)")
    m = re.search(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b", task_text)
    if m:
        return m.group(0)
    m = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", task_text)
    if m:
        return m.group(0)
    return ""


def _extract_quoted(task_text: str) -> str:
    m = re.search(r'["\']([^"\']{3,})["\']', task_text)
    return m.group(1) if m else ""


def _public_methods(agent: Any) -> List[str]:
    out = []
    for name in dir(agent):
        if name.startswith("_") or name in _SKIP_METHODS:
            continue
        try:
            if callable(getattr(agent, name, None)):
                out.append(name)
        except Exception:
            continue
    return sorted(out)


def _match_methods(task_text: str, methods: List[str]) -> List[str]:
    t = task_text.lower()
    # Extract words worth matching (skip tiny stop-words)
    stop = {"the", "a", "an", "for", "and", "or", "of", "to", "in", "on", "with",
            "my", "me", "is", "are", "do", "does", "please", "can", "you", "it",
            "this", "that", "run", "using", "use"}
    task_words = {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 2 and w not in stop}
    scored: List[Tuple[float, str]] = []
    for meth in methods:
        score = 0.0
        ml = meth.lower()
        # 1. Every word of the method name that appears in the task counts.
        meth_words = [w for w in re.findall(r"[a-z0-9]+", ml) if len(w) > 2]
        if meth_words:
            hits = sum(1 for w in meth_words if w in task_words)
            if hits:
                score += 1.5 * hits
                # Full-name coverage bonus (e.g. check + rate + limit all present)
                if hits == len(meth_words):
                    score += 3.0
        # 2. Keyword hints ("scan" → scan_*, "chart" → chart_*)
        for word, frag in _KEYWORD_HINTS.items():
            if word in t and frag in ml:
                score += 1.0
        # 3. Explicit method-name mention in the task ("run scan_ports on …")
        if re.search(r"\b" + re.escape(ml.replace("_", r"[ _]")) + r"\b", t):
            score += 5.0
        if score > 0:
            scored.append((score, meth))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [m for _, m in scored]


def _call_with_best_effort(agent: Any, method_name: str, task_text: str,
                           agent_name: str) -> Tuple[bool, Any]:
    """Invoke a legacy method, deriving arguments from the task text and the
    method signature. Returns (called, result)."""
    meth = getattr(agent, method_name, None)
    if meth is None:
        return False, None
    try:
        sig = inspect.signature(meth)
    except (TypeError, ValueError):
        sig = None

    target = _extract_target(task_text)
    quoted = _extract_quoted(task_text)

    kwargs: Dict[str, Any] = {}
    args: List[Any] = []
    if sig is not None:
        for pname, param in sig.parameters.items():
            if pname in ("self", "cls"):
                continue
            lower = pname.lower()
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            if lower in ("target", "url", "host", "domain", "endpoint", "site", "ip", "address"):
                kwargs[pname] = target or quoted or agent_name
            elif lower in ("query", "q", "search", "text", "prompt", "request", "input",
                           "description", "task", "content", "message", "name", "title"):
                kwargs[pname] = quoted or task_text
            elif lower in ("code", "script", "source"):
                m = re.search(r"```(?:\w+)?\n(.*?)```", task_text, re.DOTALL)
                kwargs[pname] = m.group(1) if m else task_text
            elif param.default is not inspect.Parameter.empty:
                continue  # keep default
            else:
                kwargs[pname] = quoted or target or task_text

    try:
        if kwargs:
            result = meth(**kwargs)
        elif sig is not None and all(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                                     or p.default is not inspect.Parameter.empty
                                     or p.name in ("self", "cls") for p in sig.parameters.values()):
            result = meth()
        else:
            result = meth()
        return True, result
    except TypeError:
        # Signature mismatch — try zero-arg call.
        try:
            return True, meth()
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _serialize(result: Any) -> str:
    if isinstance(result, str):
        return result
    if result is None:
        return ""
    if hasattr(result, "to_dict"):
        try:
            return json.dumps(result.to_dict(), default=str, indent=2)
        except Exception:
            pass
    try:
        return json.dumps(result, default=str, indent=2)
    except Exception:
        return str(result)


def run_agent_task(agent_name: str, task: Any) -> Dict[str, Any]:
    """Run a task on any agent. `task` is a description string or a payload
    dict. Returns a dict with success/output/metadata — real output only."""
    agent_name = str(agent_name or "").strip()
    started = time.time()
    task_text = task if isinstance(task, str) else json.dumps(task, default=str)
    if not task_text.strip():
        return {"success": False, "error": "empty task", "output": ""}

    agent = load_agent(agent_name)
    if agent is None:
        return {"success": False,
                "error": (f"Agent '{agent_name}' could not be loaded. Available: "
                          f"{', '.join(sorted(AGENT_FILES.keys()))}"),
                "output": ""}

    # ── Path 1: BaseAgent subclass → Task → execute()
    try:
        from core.base_agent import BaseAgent, Task
        if isinstance(agent, BaseAgent):
            payload = task if isinstance(task, dict) else {
                "original_request": task_text, "request": task_text, "target": _extract_target(task_text)}
            t = Task(agent_name=agent_name, description=task_text, payload=payload)
            result = agent.execute(t)
            out = result.output if hasattr(result, "output") else result
            ok = bool(result.success) if hasattr(result, "success") else True
            return {
                "success": ok,
                "agent": agent_name,
                "output": _serialize(out) or (result.error if hasattr(result, "error") else ""),
                "error": getattr(result, "error", None),
                "execution_time": round(time.time() - started, 2),
                "path": "base_agent",
            }
    except ImportError:
        pass
    except Exception as e:
        return {"success": False, "agent": agent_name, "error": f"{type(e).__name__}: {e}",
                "output": "", "path": "base_agent"}

    # ── Path 2: generic execute/handle_task/process interfaces
    for iface in ("execute", "handle_task", "process"):
        fn = getattr(agent, iface, None)
        if not callable(fn):
            continue
        try:
            payload = task if isinstance(task, dict) else {
                "original_request": task_text, "request": task_text,
                "target": _extract_target(task_text), "description": task_text}
            result = fn(payload)
            ok = True
            if isinstance(result, dict):
                ok = bool(result.get("success", result.get("ok", True)))
            return {"success": ok, "agent": agent_name, "output": _serialize(result),
                    "execution_time": round(time.time() - started, 2), "path": iface}
        except Exception as e:
            logger.warning("[adapter] %s.%s failed: %s", agent_name, iface, e)
            break  # fall through to legacy dispatch

    # ── Path 3: legacy keyword dispatch onto real methods
    methods = _public_methods(agent)
    matches = _match_methods(task_text, methods)
    attempts: List[str] = []
    for meth in matches[:4]:
        called, result = _call_with_best_effort(agent, meth, task_text, agent_name)
        if called:
            out = _serialize(result)
            ok = True
            if isinstance(result, dict):
                ok = bool(result.get("success", result.get("ok", True)))
            return {"success": ok, "agent": agent_name, "output": out or "(method returned nothing)",
                    "method": meth, "execution_time": round(time.time() - started, 2),
                    "path": "legacy_dispatch"}
        attempts.append(f"{meth}: {result}")

    # ── Path 4: honest capability report (never fake results)
    health = {}
    if callable(getattr(agent, "health", None)):
        try:
            health = agent.health() or {}
        except Exception:
            health = {}
    codename = getattr(agent, "CODENAME", agent_name.upper())
    cap_note = (f"{codename} has no method matching this task. "
                f"Real capabilities: {', '.join(methods[:25]) or 'none exposed'}. "
                f"Rephrase the task using one of these capabilities.")
    return {
        "success": False,
        "agent": agent_name,
        "error": cap_note,
        "output": (f"AGENT {codename} — capability report\n"
                   f"health: {json.dumps(health, default=str)[:400]}\n"
                   f"matched methods: {matches[:10] or 'none'}\n"
                   f"available methods: {', '.join(methods[:25])}\n"
                   + (f"attempt errors: {'; '.join(attempts)}\n" if attempts else "")),
        "execution_time": round(time.time() - started, 2),
        "path": "capability_report",
    }
