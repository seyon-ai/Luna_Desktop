"""Planner: turns a goal into a structured, adaptive plan.

Plans are best-effort and always re-observed by the agent; the planner is not
treated as a fixed click script.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PlanStep:
    id: int
    description: str
    expected: str = ""
    status: str = "pending"  # pending|running|verified|failed|skipped

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "summary": self.summary,
            "steps": [s.to_dict() for s in self.steps],
        }

    @property
    def current_step(self) -> PlanStep | None:
        for step in self.steps:
            if step.status == "pending":
                return step
        return None

    def mark(self, step_id: int, status: str, note: str = "") -> None:
        for step in self.steps:
            if step.id == step_id:
                step.status = status
                if note:
                    step.expected = note
                return

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status in ("verified", "failed", "skipped"))
        return round(done / len(self.steps) * 100.0, 1)


def default_plan(goal: str) -> Plan:
    """A generic, observation-first plan used when the LLM does not return steps."""
    return Plan(
        goal=goal,
        steps=[
            PlanStep(1, "Understand the goal and define success criteria."),
            PlanStep(2, "Choose the tools needed for the task."),
            PlanStep(3, "Execute the first action and observe the result."),
            PlanStep(4, "Verify the expected state; adapt if the UI changed."),
            PlanStep(5, "Complete remaining steps, verifying each outcome."),
            PlanStep(6, "Summarize the result for the user."),
        ],
    )
