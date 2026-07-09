import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Action = Literal["goto", "fill", "click", "assert_text"]
Mode = Literal["deterministic", "agentic"]
PromotionStatus = Literal["pending", "approved", "rejected"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestStep(BaseModel):
    step_id: str = Field(default_factory=lambda: new_id("step"))
    order: int
    action: Action
    selector: Optional[str] = None
    value: Optional[str] = None
    # Human-readable description of what this step is trying to accomplish
    # and what "success" looks like. This is what the agentic executor
    # falls back to when the selector no longer resolves, and what powers
    # the customer-facing narrative.
    expected: str


class TestCase(BaseModel):
    test_id: str = Field(default_factory=lambda: new_id("test"))
    intent: str
    created_at: str = Field(default_factory=now_iso)
    steps: list[TestStep]


class StepResult(BaseModel):
    step_id: str
    order: int
    action: Action
    mode: Mode
    selector_used: Optional[str] = None
    value_used: Optional[str] = None
    success: bool
    latency_ms: float
    error: Optional[str] = None
    agent_reasoning: Optional[str] = None
    customer_narrative: str


class RunTrace(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("run"))
    test_id: str
    started_at: str = Field(default_factory=now_iso)
    finished_at: Optional[str] = None
    overall_success: bool = False
    steps: list[StepResult] = Field(default_factory=list)
    promotion_ids: list[str] = Field(default_factory=list)


class PromotionCandidate(BaseModel):
    promotion_id: str = Field(default_factory=lambda: new_id("promo"))
    run_id: str
    test_id: str
    step_id: str
    old_selector: Optional[str]
    new_selector: str
    new_action: Action
    new_value: Optional[str] = None
    reasoning: str
    status: PromotionStatus = "pending"
    created_at: str = Field(default_factory=now_iso)
