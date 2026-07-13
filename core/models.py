"""IRIS v1 Core Models — Structured Output & Tool Schemas"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal

class PlanStep(BaseModel):
    step: int = Field(..., description="Step number in sequence")
    description: str = Field(..., description="What this step does")
    tool: str = Field(..., description="Tool name to execute")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    expected_output: Optional[str] = Field(None, description="What success looks like")

class ReasoningPlan(BaseModel):
    type: Literal["direct_answer", "requires_tools"] = Field(..., description="Task classification")
    thoughts: str = Field(..., description="Step-by-step reasoning process")
    plan_summary: str = Field(..., description="Brief description of approach")
    plan: List[PlanStep] = Field(default_factory=list, description="Step-by-step execution plan")
    estimated_minutes: int = Field(5, ge=1, le=120, description="Time estimate")
    priority: int = Field(5, ge=1, le=10, description="Priority 1-10")
    tools_needed: List[str] = Field(default_factory=list, description="Required tools")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Confidence in plan")

class ToolCall(BaseModel):
    tool: str = Field(..., description="Tool name")
    params: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    reasoning: str = Field(..., description="Why this tool was chosen")

class ToolResult(BaseModel):
    success: bool = Field(..., description="Whether execution succeeded")
    data: Optional[Any] = Field(None, description="Result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    output: Optional[str] = Field(None, description="Console/output text")
    duration: float = Field(0.0, description="Execution time in seconds")
    tool: str = Field(..., description="Tool that was called")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters used")

class VerificationResult(BaseModel):
    success: bool = Field(..., description="All checks passed")
    total_steps: int = Field(0, description="Total steps executed")
    successful_steps: int = Field(0, description="Steps that succeeded")
    failed_steps: List[ToolResult] = Field(default_factory=list, description="Failed steps")
    total_duration: float = Field(0.0, description="Total execution time")
    checks: List[Dict[str, Any]] = Field(default_factory=list, description="Additional checks")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")

class ExperienceRecord(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    user_input: str = Field(..., description="Original request")
    plan: ReasoningPlan = Field(..., description="Plan that was generated")
    results: List[ToolResult] = Field(default_factory=list, description="Execution results")
    verification: VerificationResult = Field(..., description="Verification outcome")
    success: bool = Field(..., description="Overall task success")
    lesson: str = Field(..., description="What was learned from this task")
    emotion: str = Field("neutral", description="Emotional context")
    timestamp: str = Field(..., description="When this happened")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")

class Skill(BaseModel):
    name: str = Field(..., description="Skill identifier")
    description: str = Field(..., description="What this skill does")
    trigger_patterns: List[str] = Field(default_factory=list, description="Keywords that trigger this skill")
    plan_template: ReasoningPlan = Field(..., description="Reusable plan template")
    success_count: int = Field(0, description="Times this skill succeeded")
    failure_count: int = Field(0, description="Times this skill failed")
    created_at: str = Field(..., description="When skill was extracted")
    last_used: Optional[str] = Field(None, description="Last usage timestamp")

class StatusUpdate(BaseModel):
    phase: str = Field(..., description="Current phase")
    message: str = Field(..., description="Human-readable status")
    progress: int = Field(0, ge=0, le=100, description="Progress percentage")
    final: bool = Field(False, description="Is this the final update")
    timestamp: str = Field(..., description="ISO timestamp")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")
