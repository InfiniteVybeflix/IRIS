"""IRIS Autonomous Self-Healing Loop
=====================================

This is the crown jewel of IRIS v3 — the self-healing execution loop
that lets IRIS attempt a multi-step task, investigate failures, fix
them, and retry until success (or give up gracefully after N attempts).

Pattern:
    ┌─ plan       (cortex.planner breaks the task into ordered steps)
    ├─ execute    (OMNIS.execute dispatches each step to a capability)
    ├─ verify     (check the step produced expected output)
    ├─ on fail:   ┌─ investigate  (auto_debug analyzes the error)
    │             ├─ fix          (apply the suggested fix)
    │             └─ retry        (re-execute the step, up to MAX_RETRIES)
    └─ report     (full trajectory with timings, errors, fixes applied)

Inspired by:
  - Hermes Agent's "closed learning loop" (skill self-improvement)
  - ClosePaw's autonomous retry on action failures
  - Claude's "computer use" verify-and-retry pattern

Exposed as:
  - capability `autonomous_build` (skill: autonomous_tools)
  - HTTP endpoint POST /api/iris/autonomous
  - direct module API: from modules.autonomous_loop import run_autonomous_task
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tunables
MAX_RETRIES_PER_STEP = 3
MAX_TOTAL_STEPS = 25
STEP_TIMEOUT_SECONDS = 120


@dataclass
class StepResult:
    """Outcome of one execution attempt of one step."""
    step_index: int
    step_description: str
    capability: str
    params: Dict[str, Any]
    attempt: int  # 1 = first try, 2 = first retry, etc.
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: int = 0
    fix_applied: str = ""  # description of the fix (if any)


@dataclass
class Trajectory:
    """Full record of an autonomous task — used for transparency + debugging."""
    task: str
    started_at: str
    finished_at: str = ""
    plan: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[StepResult] = field(default_factory=list)
    overall_success: bool = False
    total_duration_ms: int = 0
    final_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "plan_steps": len(self.plan),
            "total_step_attempts": len(self.steps),
            "successful_steps": sum(1 for s in self.steps if s.success),
            "overall_success": self.overall_success,
            "total_duration_ms": self.total_duration_ms,
            "final_summary": self.final_summary,
            "plan": self.plan,
            "steps": [
                {
                    "step": s.step_index,
                    "description": s.step_description,
                    "capability": s.capability,
                    "attempt": s.attempt,
                    "success": s.success,
                    "error": s.error,
                    "fix_applied": s.fix_applied,
                    "duration_ms": s.duration_ms,
                    "output_preview": str(s.output)[:500] if s.output else "",
                }
                for s in self.steps
            ],
        }


# ─── Planning ──────────────────────────────────────────────────────────

def plan_task(task: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Break a high-level task into ordered steps.

    Uses keyword-based heuristics when no LLM is available; falls back
    to a generic scaffold-and-test plan. When llm_router is configured
    with a working backend, we use it for richer planning.
    """
    task_lower = task.lower()
    context = context or {}

    # Try LLM-driven planning first
    try:
        from core.llm_router import llm_router
        plan_prompt = f"""You are IRIS, an autonomous AI agent. Break this task into ordered steps.

Task: {task}

For each step, return JSON with: {{step, capability, params, verify}}.
Available capabilities (call OMNIS.execute with these):
- git_clone {{repo_url, target_path}}
- execute_shell {{command}}
- execute_python {{code}}
- write_file {{path, content}}
- read_file {{path}}
- list_directory {{path}}
- browse_url {{url}}
- code_generation {{description, language}}
- code_review {{code, language}}
- cybersecurity {{method:scan_vulns, target}}
- vercel_deploy {{project_path}}
- git_push {{repo_path, message}}

Return ONLY a JSON array of steps. Max 8 steps."""
        resp = llm_router.chat(
            messages=[
                {"role": "system", "content": "You are a task planner. Respond with JSON only."},
                {"role": "user", "content": plan_prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        content = resp.content if hasattr(resp, "content") else str(resp)
        # Extract JSON array from response
        match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', content)
        if match:
            plan = json.loads(match.group(0))
            if isinstance(plan, list) and len(plan) > 0:
                return plan[:MAX_TOTAL_STEPS]
    except Exception as e:
        logger.debug("LLM planning failed, falling back to heuristics: %s", e)

    # Heuristic planning fallback
    plan = []
    if "clone" in task_lower and "repo" in task_lower:
        repo_match = re.search(r'(https?://github\.com/[\w-]+/[\w.-]+\.git)', task)
        repo_url = repo_match.group(1) if repo_match else "https://github.com/octocat/Hello-World.git"
        target = "/tmp/iris-task-repo"
        plan.append({"step": 1, "description": "Clone repository", "capability": "git_clone", "params": {"repo_url": repo_url, "target_path": target}, "verify": "list_directory {path:" + target + "}"})
        plan.append({"step": 2, "description": "List cloned files", "capability": "list_directory", "params": {"path": target}, "verify": "count > 0"})
        return plan

    if "scan" in task_lower and ("vuln" in task_lower or "security" in task_lower):
        target_match = re.search(r'(https?://[^\s,]+)', task)
        target = target_match.group(1) if target_match else "https://httpbin.org"
        plan.append({"step": 1, "description": "Scan for vulnerabilities", "capability": "cybersecurity", "params": {"method": "scan_vulns", "target": target}, "verify": "success=true"})
        return plan

    if "deploy" in task_lower:
        plan.append({"step": 1, "description": "List project files", "capability": "list_directory", "params": {"path": "."}, "verify": "count > 0"})
        plan.append({"step": 2, "description": "Deploy to Vercel", "capability": "vercel_deploy", "params": {"project_path": "."}, "verify": "url is not empty"})
        return plan

    # Default: echo the task as a single step
    plan.append({"step": 1, "description": task, "capability": "execute_shell", "params": {"command": f"echo 'Executing: {task}'"}, "verify": "exit_code=0"})
    return plan


# ─── Execution + verification + self-healing ──────────────────────────

def _execute_step(capability: str, params: Dict[str, Any], omnis: Any) -> Tuple[bool, Any, str]:
    """Execute one capability via OMNIS. Returns (success, result, error)."""
    try:
        result = omnis.execute(capability, params)
        if isinstance(result, dict):
            success = result.get("success", False)
            inner = result.get("result", result)
            inner_success = inner.get("success", True) if isinstance(inner, dict) else True
            return (success and inner_success), result, ""
        return True, result, ""
    except Exception as e:
        return False, None, str(e)


def _verify_step(verify_spec: str, result: Any) -> bool:
    """Check whether the step's output matches the verify spec.

    Verify spec format: "<capability> {<json params>}" OR a simple
    expression like "success=true", "count > 0", "exit_code=0".
    """
    if not verify_spec:
        return True  # no verification requested
    if result is None:
        return False
    result_dict = result if isinstance(result, dict) else {"value": result}
    inner = result_dict.get("result", result_dict)
    if not isinstance(inner, dict):
        inner = {"value": inner}

    # Simple expression: "key=value" or "key > N" or "key is not empty"
    if "=" in verify_spec and "{" not in verify_spec:
        key, _, expected = verify_spec.partition("=")
        key = key.strip()
        expected = expected.strip()
        actual = str(inner.get(key, result_dict.get(key, "")))
        return actual == expected or actual == "True" and expected.lower() == "true"
    if ">" in verify_spec and "{" not in verify_spec:
        key, _, expected = verify_spec.partition(">")
        try:
            return int(inner.get(key.strip(), 0)) > int(expected.strip())
        except (ValueError, TypeError):
            return False
    if "is not empty" in verify_spec:
        # check that some field has content
        for v in [*inner.values(), *result_dict.values()]:
            if v:
                return True
        return False
    # If verify spec is itself a capability call, execute it
    if "{" in verify_spec:
        try:
            cap_match = re.match(r'(\w+)\s+(\{[\s\S]*\})', verify_spec)
            if cap_match:
                cap = cap_match.group(1)
                params_str = cap_match.group(2)
                # Replace placeholder values with actual from result
                params_str = params_str.replace("{path:", "{\"path\":")
                params = json.loads(params_str)
                # Execute via omnis
                from core.bootstrap import iris_core
                if iris_core and hasattr(iris_core, "omnis"):
                    sub_result = iris_core.omnis.execute(cap, params)
                    if isinstance(sub_result, dict):
                        return sub_result.get("success", False)
        except Exception as e:
            logger.debug("verify sub-execution failed: %s", e)
            return False
    return True


def _investigate_failure(step_description: str, capability: str, params: Dict[str, Any],
                         error: str, output: Any) -> str:
    """Use the LLM (if configured) to suggest a fix for the failed step."""
    try:
        from core.llm_router import llm_router
        diagnosis_prompt = f"""You are IRIS's autonomous debugger. A step failed.

Task step: {step_description}
Capability called: {capability}
Parameters: {json.dumps(params, default=str)[:500]}
Error: {error[:500]}
Output: {json.dumps(output, default=str)[:500] if output else 'none'}

Suggest a ONE-LINE fix. Format: <field>=<new_value>
Example: command=echo fixed
Example: target_path=/tmp/iris-repo-v2

Return ONLY the fix line, no explanation. If no fix is possible, return: GIVE_UP"""
        resp = llm_router.fast_response(diagnosis_prompt)
        fix = resp.strip()
        if fix and fix != "GIVE_UP" and "=" in fix:
            return fix
    except Exception as e:
        logger.debug("LLM investigation failed: %s", e)
    return ""


def _apply_fix(params: Dict[str, Any], fix_line: str) -> Tuple[Dict[str, Any], str]:
    """Apply a one-line fix to the params. Returns (new_params, description)."""
    if "=" not in fix_line:
        return params, ""
    key, _, value = fix_line.partition("=")
    key = key.strip()
    value = value.strip()
    new_params = dict(params)
    new_params[key] = value
    return new_params, f"set {key}={value[:80]}"


# ─── The main loop ────────────────────────────────────────────────────

def run_autonomous_task(task: str, context: Optional[Dict[str, Any]] = None,
                        max_retries: int = MAX_RETRIES_PER_STEP,
                        max_steps: int = MAX_TOTAL_STEPS) -> Trajectory:
    """Run a high-level task through the self-healing autonomous loop."""
    from datetime import datetime
    trajectory = Trajectory(
        task=task,
        started_at=datetime.utcnow().isoformat(),
    )
    start_time = time.time()

    # ── Phase 1: Plan ──────────────────────────────────────────────
    try:
        plan = plan_task(task, context)
        trajectory.plan = plan
        logger.info("[autonomous] planned %d steps for: %s", len(plan), task[:80])
    except Exception as e:
        trajectory.final_summary = f"Planning failed: {e}"
        trajectory.finished_at = datetime.utcnow().isoformat()
        trajectory.total_duration_ms = int((time.time() - start_time) * 1000)
        return trajectory

    # Get OMNIS instance
    try:
        from core.runtime import get_omnis
        omnis = get_omnis()
    except ImportError:
        omnis = None
    if not omnis:
        trajectory.final_summary = "OMNIS not available — cannot execute steps"
        trajectory.finished_at = datetime.utcnow().isoformat()
        trajectory.total_duration_ms = int((time.time() - start_time) * 1000)
        return trajectory

    # ── Phase 2: Execute each step with self-healing ─────────────
    for i, step in enumerate(plan[:max_steps]):
        step_desc = step.get("description", step.get("step", f"Step {i+1}"))
        capability = step.get("capability", "execute_shell")
        params = step.get("params", {})
        verify_spec = step.get("verify", "")

        logger.info("[autonomous] step %d: %s (capability=%s)", i+1, step_desc, capability)

        for attempt in range(1, max_retries + 2):  # 1..max_retries+1
            step_start = time.time()
            success, output, error = _execute_step(capability, params, omnis)
            duration_ms = int((time.time() - step_start) * 1000)

            if success and _verify_step(verify_spec, output):
                trajectory.steps.append(StepResult(
                    step_index=i, step_description=step_desc,
                    capability=capability, params=params, attempt=attempt,
                    success=True, output=output, duration_ms=duration_ms,
                ))
                logger.info("[autonomous] ✓ step %d attempt %d succeeded (%dms)", i+1, attempt, duration_ms)
                break
            else:
                # Failure — investigate + fix + retry
                fix_line = _investigate_failure(step_desc, capability, params, error, output)
                fix_desc = ""
                if fix_line and attempt <= max_retries:
                    new_params, fix_desc = _apply_fix(params, fix_line)
                    trajectory.steps.append(StepResult(
                        step_index=i, step_description=step_desc,
                        capability=capability, params=params, attempt=attempt,
                        success=False, output=output, error=error,
                        duration_ms=duration_ms, fix_applied=fix_desc,
                    ))
                    params = new_params
                    logger.warning("[autonomous] ✗ step %d attempt %d failed (%s) → fix: %s, retrying", i+1, attempt, error[:80], fix_desc)
                else:
                    trajectory.steps.append(StepResult(
                        step_index=i, step_description=step_desc,
                        capability=capability, params=params, attempt=attempt,
                        success=False, output=output, error=error,
                        duration_ms=duration_ms, fix_applied="GIVE_UP",
                    ))
                    logger.error("[autonomous] ✗ step %d failed permanently after %d attempts", i+1, attempt)
                    trajectory.final_summary = f"Step {i+1} ({step_desc}) failed after {attempt} attempts. Last error: {error[:200]}"
                    trajectory.overall_success = False
                    trajectory.finished_at = datetime.utcnow().isoformat()
                    trajectory.total_duration_ms = int((time.time() - start_time) * 1000)
                    return trajectory

    # All steps succeeded
    trajectory.overall_success = True
    trajectory.final_summary = f"Completed all {len(plan)} steps successfully"
    trajectory.finished_at = datetime.utcnow().isoformat()
    trajectory.total_duration_ms = int((time.time() - start_time) * 1000)
    logger.info("[autonomous] ✓ task completed in %dms: %s", trajectory.total_duration_ms, task[:80])
    return trajectory


# Convenience entry point for OMNIS dispatch
def execute_autonomous_build(params: Dict[str, Any]) -> Dict[str, Any]:
    """OMNIS-callable wrapper. Params: {task: str, context?: dict, max_retries?: int}"""
    task = params.get("task", "")
    if not task:
        return {"success": False, "error": "task required"}
    context = params.get("context", {})
    max_retries = int(params.get("max_retries", MAX_RETRIES_PER_STEP))
    trajectory = run_autonomous_task(task, context, max_retries=max_retries)
    return trajectory.to_dict()
