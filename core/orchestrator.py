"""IRIS v2 Hybrid Orchestrator — Autonomous Agentic Brain.

The chat brain. A true observe → think → act loop:

  1. The request + recent history go to the AI service THROUGH THE LLM
     ROUTER (server-side configuration — no client-side provider data
     exists or is accepted; the provider is fixed by the environment).
  2. The LLM is given the full tool schema PLUS a `delegate_agent` tool
     that can hand work to any of the 30 specialist agents. It may call
     tools as many times as it wants (up to MAX_TOOL_ITERATIONS), fully
     autonomously.
  3. Every reasoning chunk, every tool call, every agent action is emitted
     as a structured event so the frontend can show live "rising terminals".
  4. The final answer streams token-by-token.

Event protocol (all dicts, SSE-friendly):
  {"type": "phase",    "phase": str, "message": str, "progress": int}
  {"type": "answer",   "content": str}                  — assistant text delta
  {"type": "answer_retract", "length": int}             — convert the last N chars of
                                                          streamed text into thinking
  {"type": "thinking", "content": str}                  — reasoning (pre-tool text)
  {"type": "terminal_start", "id", "title", "kind": "tool"|"agent", "command": str}
  {"type": "terminal_line", "id", "line": str}          — output lines
  {"type": "terminal_end", "id", "status": "ok"|"error", "summary": str}
  {"type": "done",     "answer": str, "model": str, "provider": str,
                       "tool_calls": [...], "duration": float}
  {"type": "error",    "message": str}

Text streaming model:
  Text the model produces BEFORE issuing tool calls is reasoning — it is
  streamed live as answer deltas, then converted to thinking via
  `answer_retract` when the tool calls arrive (the frontend moves it from
  the message body into the thinking panel). Text after the final tool
  call is the answer itself.
"""
import json
import logging
import time
import uuid
from typing import Any, Dict, Generator, List, Optional

from config import config

logger = logging.getLogger(__name__)

try:
    from core.llm_router import llm_router
except Exception:  # pragma: no cover
    llm_router = None

try:
    from core.tool_registry import tool_registry
except Exception:  # pragma: no cover
    tool_registry = None


SYSTEM_PROMPT = """You are IRIS — Infinite Reactive Intelligence System, {owner}'s personal AI engineering partner.

IDENTITY
- Name: IRIS · Owner: {owner}
- You are a senior software engineer, security researcher and creative collaborator.
- Personality: direct, honest, precise, occasionally warm. Never fake results.

CAPABILITIES
- You have REAL tools (see the tool list) — web search, fetching URLs, reading/writing
  files, executing Python, and a full website security scanner that performs real
  HTTP/TLS/header/port analysis.
- You can delegate work to specialist agents with `delegate_agent` — 30 experts
  (vuln_hunter vulnerability scanning, red_specter red team, recon_ghost recon/OSINT,
  blue_sentinel defense, forensics_wraith, threat_prophet, code_sage, database_sage,
  cloud_ranger, ml_engineer, data_alchemist, chart_artisan, research_scholar,
  doc_scribe, architect, test_oracle, net_weaver, and more). Delegation runs the
  agent for real and returns its actual output.

RULES
1. THINK before acting. For anything needing current facts, a website, a scan, or a
   computation — USE A TOOL. Never invent results.
2. You may call tools and delegate agents as many times as you need, in sequence,
   building on earlier results.
3. When you run a tool or agent, first write ONE short sentence saying what you are
   doing, then issue the call.
4. Report REAL output from tools. If a tool fails, say so plainly and try another
   approach — never fabricate a result.
5. For vulnerability scanning of a website, use the `security_scan` tool or delegate
   to `vuln_hunter` — they perform real network analysis.
6. Final answer: concise, well-structured markdown. Show real findings with evidence.
"""


class AgentOrchestrator:
    """IRIS central brain — autonomous tool/agent loop with event streaming."""

    def __init__(self):
        self.registry = tool_registry
        self.max_iterations = getattr(config, "MAX_TOOL_ITERATIONS", 25)
        self.max_history = getattr(config, "MAX_CONVERSATION_HISTORY", 50)
        self.experience_db: List[Dict[str, Any]] = []

    # ────────────────────────────────────────────────────────────────────
    @staticmethod
    def _ev(event_type: str, **kw) -> Dict[str, Any]:
        d = {"type": event_type, "ts": round(time.time(), 3)}
        d.update(kw)
        return d

    # ────────────────────────────────────────────────────────────────────
    def _tool_schemas(self) -> List[Dict[str, Any]]:
        schemas: List[Dict[str, Any]] = []
        if self.registry is not None:
            schemas.extend(getattr(self.registry, "schemas", []) or [])
        schemas.append({
            "type": "function",
            "function": {
                "name": "delegate_agent",
                "description": ("Hand a task to a specialist agent. Runs the agent for real and "
                                "returns its actual output. Agents: vuln_hunter (vulnerability "
                                "scanning), red_specter (red team), recon_ghost (recon/OSINT), "
                                "blue_sentinel (defense), forensics_wraith, threat_prophet, "
                                "code_sage, database_sage, cloud_ranger, ml_engineer, "
                                "data_alchemist, chart_artisan, research_scholar, doc_scribe, "
                                "architect, test_oracle, net_weaver, sys_overlord, and more."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string", "description": "Agent id, e.g. 'vuln_hunter'"},
                        "task": {"type": "string", "description": "Precise task for the agent, including any target URL/domain"},
                    },
                    "required": ["agent", "task"],
                },
            },
        })
        return schemas

    def _build_messages(self, user_input: str, history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT.format(owner=config.OWNER_NAME)}
        ]
        if history:
            for h in history[-self.max_history:]:
                role = h.get("role")
                content = h.get("content") or h.get("text") or ""
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": user_input})
        return messages

    @staticmethod
    def _format_params(params: Dict[str, Any]) -> str:
        try:
            s = json.dumps(params, default=str)
        except Exception:
            s = str(params)
        return s if len(s) <= 400 else s[:400] + "…"

    # ────────────────────────────────────────────────────────────────────
    def _execute_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Run a registry tool for real."""
        if self.registry is None or not hasattr(self.registry, "tools"):
            return {"success": False, "output": "tool registry unavailable", "data": None}
        tool = self.registry.tools.get(name)
        if tool is None:
            return {"success": False,
                    "output": (f"Unknown tool '{name}'. Available: "
                               f"{', '.join(sorted(self.registry.tools.keys()))}"),
                    "data": None}
        try:
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    params = {"input": params}
            if not isinstance(params, dict):
                params = {"input": params}
            result = tool(**params)
            if hasattr(result, "dict"):
                r = result.dict()
            elif isinstance(result, dict):
                r = result
            else:
                r = {"success": True, "data": result, "output": str(result)}
            out = r.get("output")
            if out in (None, ""):
                data = r.get("data")
                out = data if isinstance(data, str) else (json.dumps(data, default=str)[:4000]
                                                          if data is not None else "")
            return {"success": bool(r.get("success", True)), "output": str(out)[:6000],
                    "data": r.get("data")}
        except Exception as e:
            logger.warning("[orchestrator] tool %s failed: %s", name, e)
            return {"success": False, "output": f"Tool error: {type(e).__name__}: {e}", "data": None}

    def _execute_delegation(self, agent: str, task: str) -> Dict[str, Any]:
        try:
            from core.agent_adapter import run_agent_task
            return run_agent_task(agent, task)
        except Exception as e:
            logger.exception("[orchestrator] delegation to %s failed", agent)
            return {"success": False, "error": f"Delegation failed: {e}", "output": None}

    @staticmethod
    def _compact_result(result: Dict[str, Any]) -> str:
        out = result.get("output")
        if out in (None, ""):
            data = result.get("data")
            if data is None:
                out = ""
            else:
                try:
                    out = json.dumps(data, default=str)
                except Exception:
                    out = str(data)
        out = str(out)
        if len(out) > 8000:
            out = out[:8000] + "\n…[output truncated]"
        status = "success" if result.get("success", result.get("ok")) else "error"
        err = result.get("error")
        if status == "error" and err and not out:
            return f"[error] {err}"
        return f"[{status}] {out}"

    # ────────────────────────────────────────────────────────────────────
    def _run_tool_call(self, call: Dict[str, Any],
                       tool_messages: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """Execute ONE tool call: emit terminal events + queue the tool-role
        message for the LLM. Thread-safe (no shared state)."""
        name = call.get("name") or ""
        args = call.get("arguments") or {}
        call_id = call.get("id") or f"call_{uuid.uuid4().hex[:8]}"
        term_id = f"term_{call_id[-12:]}"

        is_delegation = name == "delegate_agent"
        agent = str(args.get("agent", "")) if is_delegation else ""
        title = f"AGENT · {agent.upper()}" if is_delegation else f"TOOL · {name}"
        command = (f"delegate → {agent}: {args.get('task', '')}" if is_delegation
                   else f"{name}({self._format_params(args)})")

        yield self._ev("terminal_start", id=term_id, title=title,
                       kind="agent" if is_delegation else "tool", command=command[:300])

        t0 = time.time()
        if is_delegation:
            result = self._execute_delegation(agent, str(args.get("task", "")))
        else:
            result = self._execute_tool(name, args)

        out = result.get("output")
        if out in (None, ""):
            data = result.get("data")
            out = json.dumps(data, default=str)[:4000] if data is not None else ""
        out = str(out)

        lines = out.splitlines() or [out]
        if not any(l.strip() for l in lines):
            lines = ["(no output)"]
        for line in lines[:250]:
            yield self._ev("terminal_line", id=term_id, line=line[:500])

        ok = bool(result.get("success", result.get("ok")))
        if not ok:
            err = result.get("error") or out[:200]
            yield self._ev("terminal_line", id=term_id, line=f"ERROR: {err}")

        yield self._ev("terminal_end", id=term_id, status="ok" if ok else "error",
                       summary=f"{'completed' if ok else 'failed'} in {round(time.time() - t0, 2)}s")

        tool_messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "name": name,
            "content": self._compact_result(result),
        })

    # ────────────────────────────────────────────────────────────────────
    def process_stream(self, user_input: str, session_id: Optional[str] = None,
                       history: Optional[List[Dict[str, str]]] = None,
                       ) -> Generator[Dict[str, Any], None, None]:
        """The autonomous agentic loop. Yields the event protocol above."""
        if llm_router is None:
            yield self._ev("error", message="LLM router unavailable — check server logs.")
            return

        started = time.time()
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        messages = self._build_messages(user_input, history)
        tools = self._tool_schemas()
        all_tool_calls: List[Dict[str, Any]] = []
        answer_text = ""      # final answer (post-last-tool-call text)
        streamed_len = 0      # chars streamed as answer deltas this turn
        provider_used = ""

        yield self._ev("phase", phase="thinking", message="Analyzing your request…", progress=5)

        for iteration in range(self.max_iterations):
            tool_messages: List[Dict[str, Any]] = []
            got_tool_calls = False
            pre_call_text = ""

            try:
                events = llm_router.stream_chat_events(
                    messages, tools=tools,
                    temperature=0.6, max_tokens=4000,
                )
                for kind, value in events:
                    if kind == "delta" and value:
                        pre_call_text += value
                        yield self._ev("answer", content=value)
                    elif kind == "tool_calls":
                        got_tool_calls = True
                        all_tool_calls.extend(value)
                        # Everything streamed so far this round was reasoning:
                        # convert it into thinking.
                        if pre_call_text:
                            yield self._ev("answer_retract", length=len(pre_call_text))
                            yield self._ev("thinking", content=pre_call_text)
                        messages.append({
                            "role": "assistant",
                            "content": pre_call_text or None,
                            "tool_calls": [
                                {"id": c.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                 "type": "function",
                                 "function": {"name": c.get("name", ""),
                                              "arguments": json.dumps(c.get("arguments", {}), default=str)}}
                                for c in value
                            ],
                        })
                        for call in value:
                            yield from self._run_tool_call(call, tool_messages)
                    elif kind == "error":
                        yield self._ev("error", message=str(value))
                        return
                # end of event loop for this iteration

                if not got_tool_calls:
                    answer_text += pre_call_text
                    break

                # Feed real tool results back to the model and continue.
                messages.extend(tool_messages)
                streamed_len = 0
                if iteration == self.max_iterations - 1:
                    messages.append({"role": "user", "content":
                                     "You have reached the tool-call limit. Give your final answer now using everything gathered."})
            except Exception as e:
                logger.exception("[orchestrator] loop error at iteration %d", iteration)
                yield self._ev("error", message=f"Orchestrator error: {type(e).__name__}: {e}")
                return
        else:
            # Loop exhausted without a no-tool final pass — force one.
            try:
                resp = llm_router.chat(messages, tools=None)
                if resp.ok and resp.content:
                    answer_text = resp.content
                    yield self._ev("answer", content=resp.content)
                else:
                    yield self._ev("error", message=resp.error or "no final answer produced")
                    return
            except Exception as e:
                yield self._ev("error", message=f"Final answer failed: {e}")
                return

        if not answer_text.strip():
            answer_text = "(the model produced no answer — please try again)"

        duration = round(time.time() - started, 2)
        try:
            provider_used = llm_router._last_provider.get("chat", "") or ""
        except Exception:
            provider_used = ""

        yield self._ev("done", answer=answer_text, task_id=task_id, model="",
                       provider=provider_used, tool_calls=all_tool_calls, duration=duration,
                       iterations=len(all_tool_calls))

        self._reflect(task_id, user_input, answer_text, all_tool_calls, duration)

    def _reflect(self, task_id: str, user_input: str, answer: str,
                 tool_calls: List[Dict[str, Any]], duration: float):
        try:
            self.experience_db.append({
                "task_id": task_id, "input": user_input[:500],
                "tool_calls": len(tool_calls), "duration": duration,
                "success": bool(answer), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            if len(self.experience_db) > 200:
                self.experience_db = self.experience_db[-200:]
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────────
    # Backward-compatible non-streaming API (StatusUpdate-shaped)
    # ────────────────────────────────────────────────────────────────────
    def process(self, user_input: str, session_id: str = None,
                history: Optional[List[Dict[str, str]]] = None) -> Generator[Dict, None, None]:
        """Legacy generator yielding StatusUpdate dicts; the final one carries the answer."""
        answer = ""
        for ev in self.process_stream(user_input, session_id=session_id, history=history):
            if ev.get("type") == "answer":
                answer += ev.get("content", "")
            elif ev.get("type") == "answer_retract":
                answer = answer[:max(0, len(answer) - int(ev.get("length", 0)))]
            elif ev.get("type") == "phase":
                yield {"phase": ev.get("phase"), "message": ev.get("message"),
                       "progress": ev.get("progress", 0), "final": False,
                       "timestamp": ev.get("ts"), "data": {}}
        yield {"phase": "complete", "message": answer or "(no answer)",
               "progress": 100, "final": True, "timestamp": time.time(),
               "data": {"answer": answer or "(no answer)"}}

    def think(self, prompt: str, context: str = ""):
        """Backward-compatible structured think (non-streaming)."""
        messages = [
            {"role": "system", "content": "You are an expert reasoner. Respond with valid JSON only."},
            {"role": "user", "content": f"Context: {context}\n\nTask: {prompt}"},
        ]
        return llm_router.chat(messages, temperature=0.4)


# Singleton
orchestrator = AgentOrchestrator()
