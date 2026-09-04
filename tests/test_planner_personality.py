from __future__ import annotations

from luna.config.config import PersonalityConfig
from luna.core.personality import build_personality_prompt
from luna.core.planner import PlanStep, default_plan


def test_default_plan_progression():
    plan = default_plan("Organize downloads")
    assert len(plan.steps) >= 5
    assert plan.current_step is not None
    plan.mark(plan.steps[0].id, "verified")
    assert plan.progress > 0
    assert plan.current_step.id == plan.steps[1].id


def test_plan_serialization():
    plan = default_plan("x")
    data = plan.to_dict()
    assert data["goal"] == "x"
    assert data["steps"][0]["description"]


def test_personality_modes():
    p = PersonalityConfig(verbosity="concise")
    prompt = build_personality_prompt(p)
    assert "concise" in prompt.lower() or "Concise".lower() in prompt.lower()

    companion = PersonalityConfig(mode="companion")
    prompt = build_personality_prompt(companion)
    assert "companion" in prompt.lower()
    assert "romantic" not in prompt.lower() or "not a romantic" in prompt.lower()

    custom = PersonalityConfig(mode="custom", custom_prompt="Speak like a librarian.")
    prompt = build_personality_prompt(custom)
    assert "librarian" in prompt


def test_personality_custom_overrides_mode():
    p = PersonalityConfig(mode="concise", custom_prompt="")
    assert "concise" in build_personality_prompt(p).lower()
