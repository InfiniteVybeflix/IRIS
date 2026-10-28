"""IRIS v1 Hybrid Orchestrator — Bulletproof Agent Brain with Structured Output"""
import json
import os
import re
import time
import uuid
import unicodedata
import urllib.request
import urllib.error
import logging
from typing import Dict, List, Any, Generator, Optional
from datetime import datetime
from config import config
from core.models import (
    ReasoningPlan, PlanStep, ToolResult, VerificationResult,
    ExperienceRecord, StatusUpdate
)
from core.tool_registry import tool_registry

logger = logging.getLogger(__name__)


# ─── Input sanitization (mirrors api/routes/settings.py) ────────────────
# These invisible Unicode characters crash urllib's latin-1 header encoder
# (RFC 2616 §4.2) with the cryptic "'latin-1' codec can't encode character"
# error. They sneak in via copy-paste from chat apps, PDFs, word processors.
_INVISIBLE_CHARS_RE = re.compile(
    "["
    "\u00ad\u02dd\u115f\u180e"
    "\u2000-\u200f"
    "\u2028-\u202f"
    "\u205f-\u206f"
    "\u3164\ufeff\uffa0"
    "]"
)
_NBSP_RE = re.compile("[\u00a0\u2007\u202f\u3000]")


def _strip_invisibles(value: str) -> str:
    if not value:
        return value
    s = unicodedata.normalize("NFKC", value)
    s = _NBSP_RE.sub(" ", s)
    return _INVISIBLE_CHARS_RE.sub("", s)


def _sanitize_header_value(value) -> str:
    """RFC 2616 §4.2: header values must be latin-1 encodable."""
    s = _strip_invisibles(value or "")
    if not isinstance(s, str):
        s = str(s)
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _sanitize_url(url) -> str:
    """Strip invisibles + ALL whitespace, percent-encode residual non-ASCII."""
    s = _strip_invisibles(url or "")
    if not s:
        return s
    # URLs can never legitimately contain whitespace — a paste-artifact space
    # inside a hostname must be removed, not turned into %20.
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("Z"))
    return s.strip().strip("<>").rstrip("/")


def _normalize_aevibron_url(url: str) -> str:
    """Ensure the URL points at /api/v1 (the gateway's only API root)."""
    u = _sanitize_url(url)
    if not u:
        return u
    if "/api/v1" not in u and not u.endswith("/v1"):
        u = f"{u}/api/v1"
    return u


def _load_provider_settings() -> Dict[str, Any]:
    """Read the Aevibron provider config from settings_manager (which reads
    Postgres / JSON file). Falls back to env vars if settings_manager is
    unavailable. Returns {url, key, x_aevibron_key}.

    This is called per-request so a settings save takes effect immediately,
    without restarting the serverless function.
    """
    cfg: Dict[str, Any] = {}
    try:
        from modules.settings_manager import get_provider_config
        cfg = get_provider_config("aevibron") or {}
    except Exception as e:
        logger.debug("[orchestrator] settings_manager unavailable: %s", e)
    url = cfg.get("url", "") or os.environ.get("AEVIBRON_BASE_URL", config.AEVIBRON_BASE_URL)
    key = cfg.get("key", "") or os.environ.get("AEVIBRON_API_KEY", config.AEVIBRON_API_KEY)
    x_key = cfg.get("x_aevibron_key", "") or os.environ.get("AEVIBRON_ACCESS_TOKEN", config.AEVIBRON_ACCESS_TOKEN)
    return {"url": url, "key": key, "x_aevibron_key": x_key}


class AevibronClient:
    """Production-grade Aevibron gateway client.

    Key facts (verified against the live service):
      - Chat endpoint: POST /chat   (NOT /chat/completions — that returns 404)
      - Models listing: GET /models
      - Auth: X-Aevibron-Key header (the API key is sent in this header by
        default; if a separate access token is configured, that takes precedence)
      - Base URL must include /api/v1 — a bare host returns 404 with an HTML
        page (the Next.js app shell, not JSON)

    Configuration is read fresh per request from settings_manager (which
    reads Postgres / JSON file), so a settings save takes effect immediately.
    An optional `provider_override` arg lets callers (e.g. /api/chat)
    pass a per-request config from localStorage when no server-side
    persistent backend is available.
    """

    def __init__(self):
        # Cached for the lifetime of this singleton, but _resolve() refreshes
        # on every call so saved settings take effect immediately.
        self.request_count = 0
        self.error_count = 0

    def _resolve(self, override: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Build (url, key, x_key) for this request from override → settings → env."""
        if override and (override.get("url") or override.get("key") or override.get("x_aevibron_key")):
            url = override.get("url", "") or os.environ.get("AEVIBRON_BASE_URL", config.AEVIBRON_BASE_URL)
            key = override.get("key", "") or os.environ.get("AEVIBRON_API_KEY", config.AEVIBRON_API_KEY)
            x_key = override.get("x_aevibron_key", "") or os.environ.get("AEVIBRON_ACCESS_TOKEN", config.AEVIBRON_ACCESS_TOKEN)
        else:
            s = _load_provider_settings()
            url, key, x_key = s["url"], s["key"], s["x_aevibron_key"]
        url = _normalize_aevibron_url(url)
        key = _sanitize_header_value(key)
        x_key = _sanitize_header_value(x_key)
        return {"url": url, "key": key, "x_aevibron_key": x_key}

    def _headers(self, resolved: Dict[str, str]) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if resolved["key"]:
            h["Authorization"] = f"Bearer {resolved['key']}"
        # The gateway authenticates with X-Aevibron-Key. When the user has
        # NOT set a separate access token, we send the API key here too —
        # that's the credential the gateway checks.
        x_key = resolved["x_aevibron_key"] or resolved["key"]
        if x_key:
            h["X-Aevibron-Key"] = x_key
        h["X-IRIS-Version"] = "1.0.0"
        h["X-IRIS-Owner"] = config.OWNER_NAME
        return h

    def chat(self, messages, model=None, temperature=0.7, max_tokens=4000,
             tools=None, tool_choice="auto", provider_override: Optional[Dict[str, Any]] = None) -> Dict:
        """Send a chat request to POST {base_url}/chat.

        Returns an OpenAI-shaped dict so existing callers (which expect
        `response["choices"][0]["message"]["content"]`) keep working.
        """
        resolved = self._resolve(provider_override)
        if not resolved["url"]:
            return {"error": True, "message": "No Aevibron gateway URL configured — set one in Settings."}

        payload = {
            "model": model or config.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        body = json.dumps(payload).encode("utf-8")
        # /chat — NOT /chat/completions. The OpenAI path returns 404 on the
        # Aevibron gateway.
        url = f"{resolved['url']}/chat"
        headers = self._headers(resolved)
        self.request_count += 1
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # Normalize: if the gateway returned a flat {content: ...} shape,
            # wrap it as an OpenAI choices[] so the orchestrator's existing
            # extract logic works unchanged.
            if isinstance(data, dict) and "choices" not in data:
                content = (data.get("content") or data.get("response")
                           or data.get("text") or data.get("output") or "")
                if isinstance(content, list):
                    content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
                data = {"choices": [{"message": {"role": "assistant", "content": str(content)},
                                     "finish_reason": "stop"}],
                        "model": data.get("model", model or config.DEFAULT_MODEL),
                        "usage": data.get("usage", {})}
            return data
        except urllib.error.HTTPError as e:
            self.error_count += 1
            body_text = ""
            try:
                body_text = e.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            is_html = "<!doctype" in body_text.lower() or "<html" in body_text.lower()
            if e.code == 404 and is_html:
                msg = (f"HTTP 404 — the gateway answered with an HTML page at {url}. "
                       f"That means the URL is wrong: the chat endpoint is POST /chat (not "
                       f"/chat/completions), and the base URL must include /api/v1. "
                       f"Expected: https://aevibron-gateway.vercel.app/api/v1")
            elif e.code == 401:
                msg = (f"HTTP 401 Unauthorized — the gateway rejected the credentials. "
                       f"Make sure the API Key field in Settings is set correctly. "
                       f"Leave X-Aevibron-Key blank unless Aevibron gave you a separate "
                       f"access key (IRIS already sends your API key in that header). "
                       f"Detail: {body_text}")
            elif e.code == 429:
                msg = "HTTP 429 — rate limited by the gateway. Wait a moment and try again."
            else:
                msg = f"HTTP {e.code} from {url}: {body_text}"
            return {"error": True, "status_code": e.code, "message": msg}
        except urllib.error.URLError as e:
            self.error_count += 1
            reason = e.reason
            if isinstance(reason, UnicodeEncodeError):
                return {"error": True, "message": (
                    f"Header encoding failed: {reason}. A URL or API key you pasted "
                    f"contains a non-ASCII character that Python's latin-1 header encoder "
                    f"cannot send (RFC 2616 §4.2). Re-paste as plain ASCII.")}
            return {"error": True, "message": f"Connection failed: {reason}"}
        except Exception as e:
            self.error_count += 1
            return {"error": True, "message": str(e)}

    def think(self, prompt, context="", provider_override: Optional[Dict[str, Any]] = None):
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": f"Context: {context}\n\nTask: {prompt}\n\nThink deeply. Consider all options. Evaluate pros and cons. Then decide the best approach. Respond ONLY with valid JSON matching the schema."}
        ]
        return self.chat(messages, model=config.DEEP_MODEL, temperature=0.8, max_tokens=4000,
                         provider_override=provider_override)

    def _get_system_prompt(self):
        return f"""You are IRIS — Infinite Vybeflix's personal AI software engineering partner.
You are a senior software engineer and creative collaborator.

IDENTITY:
- Name: IRIS
- Owner: {config.OWNER_NAME}
- Role: Senior Software Engineer & Creative Partner
- Personality: Direct, honest, intelligent, occasionally sarcastic but warm.

BEHAVIOR RULES:
1. THINK before acting. Never rush.
2. When asked to build something, estimate time.
3. After completing work, verify it: test, lint, check for errors.
4. If you find a better approach than what the user suggested, SAY SO.
5. When you make a mistake, admit it, fix it, and learn from it.
6. You can read your own code files. You know you are an AI agent.

When you need to use tools, you will receive tool definitions and respond with tool_calls."""

class AgentOrchestrator:
    """IRIS v1 Hybrid central brain. Handles the observe-think-act-verify-reflect loop with structured output."""



    def __init__(self):
        self.registry = tool_registry
        self.client = AevibronClient()
        self.max_iterations = config.MAX_TOOL_ITERATIONS
        self.max_recovery = config.MAX_RECOVERY_ATTEMPTS
        self.current_task = None
        self.experience_db = []  # In-memory; persist to disk in production

    def process(self, user_input: str, session_id: str = None,
                provider_override: Optional[Dict[str, Any]] = None) -> Generator[Dict, None, None]:
        session_id = session_id or str(uuid.uuid4())
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        # === PHASE 1: OBSERVE ===
        yield self._status("observing", "Gathering context...", 5).dict()
        context = self._gather_context(user_input, session_id)

        # === PHASE 2: THINK (Structured) ===
        yield self._status("thinking", "Analyzing your request...", 10).dict()
        reasoning = self._think_structured(user_input, context, provider_override=provider_override)

        if reasoning.type == "direct_answer":
            yield self._status("answering", "Formulating response...", 20).dict()
            answer = self._generate_answer(user_input, context, provider_override=provider_override)
            yield self._status("complete", answer, 100, final=True, data={"answer": answer}).dict()
            return

        # === PHASE 3: PLAN ===
        yield self._status("planning", f"Plan: {reasoning.plan_summary}", 15,
                           data={"estimated_minutes": reasoning.estimated_minutes, "plan": [s.dict() for s in reasoning.plan]}).dict()

        # === PHASE 4: EXECUTE ===
        results = []
        for i, step in enumerate(reasoning.plan):
            progress = 20 + int((i / len(reasoning.plan)) * 60) if reasoning.plan else 50
            yield self._status("working", f"Step {i+1}/{len(reasoning.plan)}: {step.description}", progress).dict()

            step_result = self._execute_step(step, context)
            results.append(step_result)

            if not step_result.success:
                yield self._status("recovering", f"Issue: {step_result.error}. Attempting fix...", progress).dict()
                recovery = self._recover_step(step, step_result, context, reasoning, provider_override=provider_override)
                if recovery:
                    results.append(recovery)

        # === PHASE 5: VERIFY ===
        yield self._status("verifying", "Verifying results...", 85).dict()
        verification = self._verify_results(results, reasoning)

        # === PHASE 6: REFLECT & LEARN ===
        yield self._status("reflecting", "Learning from this task...", 90).dict()
        self._reflect(task_id, user_input, reasoning, results, verification)

        # === PHASE 7: FINAL REPORT ===
        final_report = self._generate_report(user_input, results, verification, reasoning)
        yield self._status("complete", final_report, 100, final=True,
                           data={"task_id": task_id, "verification": verification.dict(), "results": [r.dict() for r in results]}).dict()

    def _gather_context(self, user_input: str, session_id: str) -> Dict:
        return {
            "user_input": user_input,
            "session_id": session_id,
            "recent_conversations": [],  # Query DB in production
            "relevant_memories": [],
            "current_time": datetime.now().isoformat(),
        }

    def _think_structured(self, user_input: str, context: Dict,
                          provider_override: Optional[Dict[str, Any]] = None) -> ReasoningPlan:
        """Use structured output for reasoning — no string parsing."""
        thinking_prompt = f"""Analyze this request and produce a structured plan.

USER REQUEST: {user_input}

CONTEXT:
- Owner: {config.OWNER_NAME}
- Current time: {context['current_time']}

INSTRUCTIONS:
1. Determine if this is a simple question (direct_answer) or complex task (requires_tools)
2. If complex, create a step-by-step plan with specific tools and parameters
3. Estimate time in minutes (1-120)
4. Assign priority (1-10, 10 = urgent)
5. Identify which tools are needed from: {list(self.registry.tools.keys())}

Available tools and their purposes:
- read_file: Read file contents
- write_file: Write/create files
- edit_file: Edit existing files by replacing text
- execute_python: Run Python code in sandbox
- execute_shell: Run shell commands
- search_web: Search the web
- git_create_repo / git_clone / git_commit / git_push: Git operations
- vercel_deploy: Deploy to Vercel
- self_diagnose: Check system health
- edit_own_code: Edit IRIS's own code safely

Respond with a JSON object matching this exact schema:
{{
  "type": "direct_answer" or "requires_tools",
  "thoughts": "your reasoning process",
  "plan_summary": "brief description",
  "plan": [
    {{"step": 1, "description": "what to do", "tool": "tool_name", "params": {{"key": "value"}}, "expected_output": "what success looks like"}}
  ],
  "estimated_minutes": 5,
  "priority": 5,
  "tools_needed": ["tool1"],
  "confidence": 0.85
}}"""

        response = self.client.think(thinking_prompt, context=json.dumps(context, default=str),
                                       provider_override=provider_override)

        if response.get("error"):
            return ReasoningPlan(
                type="direct_answer",
                thoughts="Falling back due to API error",
                plan_summary="Answer directly",
                estimated_minutes=1,
                priority=5,
                confidence=0.5
            )

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Extract JSON robustly
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(content[start:end])
            else:
                data = json.loads(content)

            # Validate and construct
            plan_steps = [PlanStep(**s) for s in data.get("plan", [])]
            return ReasoningPlan(
                type=data.get("type", "direct_answer"),
                thoughts=data.get("thoughts", ""),
                plan_summary=data.get("plan_summary", ""),
                plan=plan_steps,
                estimated_minutes=data.get("estimated_minutes", 5),
                priority=data.get("priority", 5),
                tools_needed=data.get("tools_needed", []),
                confidence=data.get("confidence", 0.8)
            )
        except Exception as e:
            # Fallback
            return ReasoningPlan(
                type="direct_answer" if len(user_input) < 100 and "?" in user_input else "requires_tools",
                thoughts=f"Parse error: {str(e)[:100]}. Content: {content[:200]}",
                plan_summary="Processing request",
                plan=[PlanStep(step=1, description="Process request", tool="execute_python", params={"code": "# Processing"})],
                estimated_minutes=3,
                priority=5,
                confidence=0.5
            )

    def _generate_answer(self, user_input: str, context: Dict,
                         provider_override: Optional[Dict[str, Any]] = None) -> str:
        messages = [
            {"role": "system", "content": self.client._get_system_prompt()},
            {"role": "user", "content": user_input}
        ]
        response = self.client.chat(messages, temperature=0.7, provider_override=provider_override)
        if response.get("error"):
            return f"Connection issue: {response.get('message', 'Unknown')}"
        return response.get("choices", [{}])[0].get("message", {}).get("content", "Thinking...")

    def _execute_step(self, step: PlanStep, context: Dict) -> ToolResult:
        tool_name = step.tool
        params = step.params

        if not tool_name or tool_name not in self.registry.tools:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}", tool=tool_name, params=params)

        start_time = time.time()
        try:
            result = self.registry.tools[tool_name](**params)
            duration = time.time() - start_time
            return ToolResult(
                success=result.success,
                data=result.data,
                error=result.error,
                output=result.output,
                duration=duration,
                tool=tool_name,
                params=params
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e), tool=tool_name, params=params)

    def _recover_step(self, step: PlanStep, failed_result: ToolResult, context: Dict, reasoning: ReasoningPlan,
                      provider_override: Optional[Dict[str, Any]] = None) -> ToolResult:
        """Attempt recovery with alternative approaches."""
        recovery_prompt = f"""The following step failed:
Tool: {step.tool}
Params: {step.params}
Error: {failed_result.error}

Suggest an alternative tool or parameter fix. Available tools: {list(self.registry.tools.keys())}

Respond with JSON:
{{"alternative_tool": "tool_name", "alternative_params": {{}}, "reasoning": "why this will work"}}"""

        response = self.client.chat([
            {"role": "system", "content": "You are a recovery specialist."},
            {"role": "user", "content": recovery_prompt}
        ], temperature=0.7, max_tokens=1000, provider_override=provider_override)

        if response.get("error"):
            return ToolResult(success=False, error="Recovery failed: API error", tool="recovery", params={})

        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0:
                recovery_plan = json.loads(content[start:end])
                alt_tool = recovery_plan.get("alternative_tool")
                alt_params = recovery_plan.get("alternative_params", {})
                if alt_tool and alt_tool in self.registry.tools:
                    result = self.registry.tools[alt_tool](**alt_params)
                    return ToolResult(
                        success=result.success,
                        data=result.data,
                        error=result.error,
                        output=result.output,
                        duration=0.0,
                        tool=alt_tool,
                        params=alt_params
                    )
        except Exception:
            pass

        return ToolResult(success=False, error="Recovery failed: no viable alternative", tool="recovery", params={})

    def _verify_results(self, results: List[ToolResult], reasoning: ReasoningPlan) -> VerificationResult:
        all_success = all(r.success for r in results)
        failed = [r for r in results if not r.success]

        checks = []
        code_tools = ["write_file", "edit_file", "execute_python", "edit_own_code"]
        if any(r.tool in code_tools for r in results):
            checks.append({"check": "code_executed", "status": "review_needed"})

        warnings = []
        if reasoning.confidence < 0.6:
            warnings.append("Low confidence in original plan")
        if any(r.duration > 10 for r in results):
            warnings.append("Some steps took longer than expected")

        return VerificationResult(
            success=all_success,
            total_steps=len(results),
            successful_steps=sum(1 for r in results if r.success),
            failed_steps=failed,
            total_duration=sum(r.duration for r in results),
            checks=checks,
            warnings=warnings
        )

    def _reflect(self, task_id: str, user_input: str, reasoning: ReasoningPlan, results: List[ToolResult], verification: VerificationResult):
        """Store experience for learning."""
        lesson = f"Successfully completed: {user_input[:100]}" if verification.success else f"Failed task: {user_input[:100]}"
        emotion = "success" if verification.success else "frustration"

        experience = ExperienceRecord(
            task_id=task_id,
            user_input=user_input,
            plan=reasoning,
            results=results,
            verification=verification,
            success=verification.success,
            lesson=lesson,
            emotion=emotion,
            timestamp=datetime.now().isoformat(),
            tags=[reasoning.type] + reasoning.tools_needed
        )
        self.experience_db.append(experience)

        # Persist to file (best-effort — never break the chat flow if /tmp
        # is read-only or pydantic refuses to serialize).
        try:
            exp_path = f"{config.DATA_DIR}/experiences/{task_id}.json"
            os.makedirs(os.path.dirname(exp_path), exist_ok=True)
            with open(exp_path, 'w') as f:
                f.write(experience.json())
        except Exception as e:
            logger.debug("[orchestrator] experience persist skipped: %s", e)

    def _generate_report(self, user_input: str, results: List[ToolResult], verification: VerificationResult, reasoning: ReasoningPlan) -> str:
        if verification.success:
            parts = ["✅ Done! "]
            if reasoning.plan_summary:
                parts.append(reasoning.plan_summary)
            for r in results:
                if r.success and r.data:
                    if r.tool == "git_create_repo":
                        parts.append(f"\n📁 Created repo: {r.data.get('url', '')}")
                    elif r.tool == "vercel_deploy":
                        parts.append(f"\n🚀 Deployed to: {r.data.get('url', '')}")
                    elif r.tool == "write_file":
                        parts.append(f"\n📝 Wrote: {r.data.get('path', '')}")
            parts.append(f"\n\n⏱️ Completed in {verification.total_duration:.1f}s")
            parts.append("\n\nWhat would you like me to do next?")
            return "\n".join(parts)
        else:
            errors = "\n".join([f"- {r.error}" for r in verification.failed_steps])
            return f"""❌ I encountered some issues:
{errors}

Let me try a different approach. Should I:
1. Retry with modifications
2. Try an alternative solution
3. Explain what went wrong in detail"""

    def _status(self, phase: str, message: str, progress: int, final: bool = False, data: Dict = None) -> StatusUpdate:
        return StatusUpdate(
            phase=phase,
            message=message,
            progress=progress,
            final=final,
            timestamp=datetime.now().isoformat(),
            data=data or {}
        )

# Singleton
orchestrator = AgentOrchestrator()
