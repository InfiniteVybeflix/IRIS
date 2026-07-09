"""IRIS v9 Hybrid Orchestrator — Bulletproof Agent Brain with Structured Output"""
import json
import time
import uuid
from typing import Dict, List, Any, Generator
from datetime import datetime
from config import config
from core.models import (
    ReasoningPlan, PlanStep, ToolResult, VerificationResult,
    ExperienceRecord, StatusUpdate
)
from core.tool_registry import tool_registry

class AevibronClient:
    """Lightweight client wrapper."""
    def __init__(self):
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.AEVIBRON_API_KEY}
        })
        self.base_url = config.AEVIBRON_BASE_URL.rstrip("/")

    def chat(self, messages, model=None, temperature=0.7, max_tokens=4000, tools=None, tool_choice="auto"):
        payload = {"model": model or config.DEFAULT_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        try:
            r = self.session.post(f"{self.base_url}/chat/completions", json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": True, "message": str(e)}

    def think(self, prompt, context=""):
        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": f"Context: {context}

Task: {prompt}

Think deeply. Consider all options. Evaluate pros and cons. Then decide the best approach. Respond ONLY with valid JSON matching the schema."}
        ]
        return self.chat(messages, model=config.DEEP_MODEL, temperature=0.8, max_tokens=4000)

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
    """IRIS v9 Hybrid central brain. Handles the observe-think-act-verify-reflect loop with structured output."""



    def _quick_diagnose(self) -> Dict:
        """Quick system health check"""
        try:
            db.get_owner()
            return {"status": "healthy", "db": "connected"}
        except Exception as e:
            return {"status": "degraded", "db": str(e)}

# Singleton
orchestrator = AgentOrchestrator()

    def _think(self, user_input: str, context: Dict) -> Dict:
        """Deep thinking — analyze request and plan approach"""

        # Build thinking prompt
        thinking_prompt = f"""Analyze this request and decide the best approach.

USER REQUEST: {user_input}

CONTEXT:
- Owner: {context['owner'].get('name', 'Unknown')}
- Recent memories: {[m['key'] for m in context['relevant_memories']]}
- System status: {context['system_status']}

INSTRUCTIONS:
1. Determine if this is a simple question (direct_answer) or a complex task (requires_tools)
2. If complex, create a step-by-step plan
3. Estimate time in minutes
4. Assign priority (1-10, 10 = urgent)
5. Identify which tools are needed

Respond in JSON format:
{{
    "type": "direct_answer" or "requires_tools",
    "thoughts": "your reasoning process",
    "plan_summary": "brief description of approach",
    "plan": [
        {{"step": 1, "description": "what to do", "tool": "tool_name", "params": {{}}}}
    ],
    "estimated_minutes": 5,
    "priority": 5,
    "tools_needed": ["tool1", "tool2"]
}}"""

        response = aevibron.think(thinking_prompt, context=json.dumps(context, default=str))

        if response.get("error"):
            # Fallback: simple direct answer
            return {
                "type": "direct_answer",
                "thoughts": "Falling back to direct answer due to API error",
                "plan_summary": "Answer directly",
                "plan": [],
                "estimated_minutes": 1,
                "priority": 5,
                "tools_needed": []
            }

        # Parse reasoning from response
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Try to extract JSON
        try:
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                reasoning = json.loads(content[start:end])
            else:
                reasoning = json.loads(content)
        except:
            # Fallback parsing
            reasoning = {
                "type": "direct_answer" if len(user_input) < 100 and "?" in user_input else "requires_tools",
                "thoughts": content[:500],
                "plan_summary": "Processing your request",
                "plan": [{"step": 1, "description": "Process request", "tool": "execute_python", "params": {"code": "# Processing"}}],
                "estimated_minutes": 3,
                "priority": 5,
                "tools_needed": []
            }

        return reasoning

    def _generate_answer(self, user_input: str, context: Dict) -> str:
        """Generate direct answer for simple questions"""
        messages = [
            {"role": "system", "content": aevibron._get_system_prompt()},
            {"role": "user", "content": user_input}
        ]

        # Add context
        if context.get("relevant_memories"):
            memory_text = "\n".join([f"- {m['key']}: {m['value']}" for m in context["relevant_memories"]])
            messages.insert(1, {"role": "system", "content": f"Relevant memories:\n{memory_text}"})

        response = aevibron.chat(messages, temperature=0.7)

        if response.get("error"):
            return f"I'm having trouble connecting to my brain right now. Error: {response.get('message', 'Unknown')}"

        return response.get("choices", [{}])[0].get("message", {}).get("content", "I'm thinking...")

    def _execute_step(self, step: Dict, context: Dict, session_id: str) -> Dict:
        """Execute a single step from the plan"""
        tool_name = step.get("tool")
        params = step.get("params", {})

        if not tool_name or tool_name not in self.registry.tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}", "step": step}

        start_time = time.time()
        result = self.registry.tools[tool_name](**params)
        duration = time.time() - start_time

        # Log the tool use
        db.log("INFO", "tool_execution", f"Executed {tool_name} in {duration:.2f}s")

        return {
            "success": result.success,
            "tool": tool_name,
            "params": params,
            "data": result.data,
            "error": result.error,
            "output": result.output,
            "duration": duration,
            "step": step
        }

    def _recover_step(self, step: Dict, failed_result: Dict, context: Dict) -> Dict:
        """Attempt to recover from a failed step"""
        # Try alternative approach
        recovery_prompt = f"""The following step failed:
Tool: {step.get('tool')}
Params: {step.get('params')}
Error: {failed_result.get('error')}

Suggest an alternative approach or fix."""

        response = aevibron.fast_response(recovery_prompt)
        # For now, just log and return
        db.log("WARNING", "recovery", f"Failed step recovery attempted: {failed_result.get('error')}")
        return {"success": False, "recovery_attempted": True, "error": failed_result.get("error")}

    def _verify_results(self, results: List[Dict], reasoning: Dict) -> Dict:
        """Verify all results are correct and complete"""
        all_success = all(r.get("success") for r in results)

        verification = {
            "success": all_success,
            "total_steps": len(results),
            "successful_steps": sum(1 for r in results if r.get("success")),
            "failed_steps": [r for r in results if not r.get("success")],
            "total_duration": sum(r.get("duration", 0) for r in results),
            "checks": []
        }

        # Run additional checks if code was involved
        code_tools = ["write_file", "edit_file", "execute_python"]
        if any(r.get("tool") in code_tools for r in results):
            verification["checks"].append({"check": "code_executed", "status": "review_needed"})

        return verification

    def _reflect(self, task_id: str, user_input: str, results: List[Dict], verification: Dict):
        """Learn from this task execution"""
        # Extract lessons
        if verification["success"]:
            lesson = f"Successfully completed: {user_input[:100]}"
            db.save_episode(lesson, context=json.dumps({"task_id": task_id}), emotion="success",
                          lesson="This approach works well")
        else:
            lesson = f"Failed task: {user_input[:100]}"
            errors = [r.get("error") for r in results if r.get("error")]
            db.save_episode(lesson, context=json.dumps({"task_id": task_id, "errors": errors}),
                          emotion="frustration", lesson="Need to improve error handling")

        # Save to memory if new pattern discovered
        tools_used = [r.get("tool") for r in results if r.get("tool")]
        if tools_used:
            db.save_memory(
                f"pattern_{task_id}",
                f"Used tools {tools_used} to: {user_input[:200]}",
                category="pattern",
                importance=6 if verification["success"] else 8
            )

    def _generate_report(self, user_input: str, results: List[Dict], 
                        verification: Dict, reasoning: Dict) -> str:
        """Generate final user-facing report"""

        if verification["success"]:
            report_parts = ["✅ Done! "]

            # Summarize what was accomplished
            if reasoning.get("plan_summary"):
                report_parts.append(reasoning["plan_summary"])

            # Add key results
            for result in results:
                if result.get("success") and result.get("data"):
                    if result.get("tool") == "git_create_repo":
                        report_parts.append(f"\n📁 Created repo: {result['data'].get('url', '')}")
                    elif result.get("tool") == "vercel_deploy":
                        report_parts.append(f"\n🚀 Deployed to: {result['data'].get('url', '')}")
                    elif result.get("tool") == "write_file":
                        report_parts.append(f"\n📝 Wrote: {result['data'].get('path', '')}")

            report_parts.append(f"\n\n⏱️ Completed in {verification.get('total_duration', 0):.1f}s")
            report_parts.append("\n\nWhat would you like me to do next?")

            return "\n".join(report_parts)
        else:
            errors = "\n".join([f"- {r.get('error', 'Unknown error')}" for r in verification.get("failed_steps", [])])
            return f"""❌ I encountered some issues:
{errors}

Let me try a different approach. Should I:
1. Retry with modifications
2. Try an alternative solution
3. Explain what went wrong in detail"""

    def _status(self, phase: str, message: str, progress: int, 
                final: bool = False, data: Dict = None) -> Dict:
        """Generate status update for UI"""
        return {
            "phase": phase,
            "message": message,
            "progress": progress,
            "final": final,
            "timestamp": datetime.now().isoformat(),
            "data": data or {}
        }

    def _quick_diagnose(self) -> Dict:
        """Quick system health check"""
        try:
            db.get_owner()
            return {"status": "healthy", "db": "connected"}
        except Exception as e:
            return {"status": "degraded", "db": str(e)}

# Singleton
orchestrator = AgentOrchestrator()

    def __init__(self):
        self.registry = tool_registry
        self.client = AevibronClient()
        self.max_iterations = config.MAX_TOOL_ITERATIONS
        self.max_recovery = config.MAX_RECOVERY_ATTEMPTS
        self.current_task = None
        self.experience_db = []  # In-memory; persist to disk in production

    def process(self, user_input: str, session_id: str = None) -> Generator[Dict, None, None]:
        session_id = session_id or str(uuid.uuid4())
        task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"

        # === PHASE 1: OBSERVE ===
        yield self._status("observing", "Gathering context...", 5).dict()
        context = self._gather_context(user_input, session_id)

        # === PHASE 2: THINK (Structured) ===
        yield self._status("thinking", "Analyzing your request...", 10).dict()
        reasoning = self._think_structured(user_input, context)

        if reasoning.type == "direct_answer":
            yield self._status("answering", "Formulating response...", 20).dict()
            answer = self._generate_answer(user_input, context)
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
                recovery = self._recover_step(step, step_result, context, reasoning)
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

    def _think_structured(self, user_input: str, context: Dict) -> ReasoningPlan:
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

        response = self.client.think(thinking_prompt, context=json.dumps(context, default=str))

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

    def _generate_answer(self, user_input: str, context: Dict) -> str:
        messages = [
            {"role": "system", "content": self.client._get_system_prompt()},
            {"role": "user", "content": user_input}
        ]
        response = self.client.chat(messages, temperature=0.7)
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

    def _recover_step(self, step: PlanStep, failed_result: ToolResult, context: Dict, reasoning: ReasoningPlan) -> ToolResult:
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
        ], temperature=0.7, max_tokens=1000)

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

        # Persist to file
        exp_path = f"{config.DATA_DIR}/experiences/{task_id}.json"
        os.makedirs(os.path.dirname(exp_path), exist_ok=True)
        with open(exp_path, 'w') as f:
            f.write(experience.json())

    def _generate_report(self, user_input: str, results: List[ToolResult], verification: VerificationResult, reasoning: ReasoningPlan) -> str:
        if verification.success:
            parts = ["✅ Done! "]
            if reasoning.plan_summary:
                parts.append(reasoning.plan_summary)
            for r in results:
                if r.success and r.data:
                    if r.tool == "git_create_repo":
                        parts.append(f"
📁 Created repo: {r.data.get('url', '')}")
                    elif r.tool == "vercel_deploy":
                        parts.append(f"
🚀 Deployed to: {r.data.get('url', '')}")
                    elif r.tool == "write_file":
                        parts.append(f"
📝 Wrote: {r.data.get('path', '')}")
            parts.append(f"

⏱️ Completed in {verification.total_duration:.1f}s")
            parts.append("

What would you like me to do next?")
            return "
".join(parts)
        else:
            errors = "
".join([f"- {r.error}" for r in verification.failed_steps])
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
