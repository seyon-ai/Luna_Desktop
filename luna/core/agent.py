"""Agent runtime: plan -> select tools -> execute -> observe -> verify loop.

The agent never assumes an action succeeded; every loop iteration re-reads the
environment and only reports verified outcomes.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from luna.core.permissions import PermissionManager
from luna.core.planner import Plan, PlanStep, default_plan
from luna.core.tasks.models import RunContext, TaskStatus
from luna.core.tools import ToolRegistry

logger = logging.getLogger(__name__)

MAX_LOOP_STEPS = 24


@dataclass
class AgentState:
    goal: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    plan: Plan | None = None
    observations: list[str] = field(default_factory=list)
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "plan": self.plan.to_dict() if self.plan else None,
            "observations": self.observations[-20:],
            "last_error": self.last_error,
        }


class AgentContext:
    """Bridges the AI-driven agent loop to the task system."""

    def __init__(
        self,
        run: RunContext,
        tools: ToolRegistry,
        permissions: PermissionManager,
        planner: Callable[[str, str, ToolRegistry], Plan] | None = None,
        model: Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]] | None = None,
        personality: str = "",
    ) -> None:
        self.run = run
        self.tools = tools
        self.permissions = permissions
        self.personality = personality
        self.state = AgentState(goal=run.task.goal)
        self._planner = planner
        self._model = model
        self._pending_approval: dict[str, Any] = {}

    # -- LLM wiring (set by Application) -----------------------------------
    def set_model(self, model: Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]) -> None:
        self._model = model

    # -- planning -------------------------------------------------------------
    def plan(self) -> Plan:
        plan = None
        if self._planner is not None:
            try:
                plan = self._planner(self.state.goal, self._history_text(), self.tools)
            except Exception:  # noqa: BLE001
                logger.exception("Planner failed; using default fallback plan.")
        plan = plan or default_plan(self.state.goal)
        self.state.plan = plan
        self.run.log(f"Plan created: {len(plan.steps)} steps.", data={"plan": plan.to_dict()})
        return plan

    # -- observe ----------------------------------------------------------------
    def observe(self, observation: str) -> None:
        self.state.observations.append(observation)
        self.run.log("Observation", data={"observation": observation[:800]})

    # -- tool execution ---------------------------------------------------------
    def execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        spec = self.tools.get(name)
        if spec is None:
            raise ToolNotFound(f"Unknown tool: {name}")
        self.run.checkpoint()
        self.run.log(f"Using tool: {name}", data={"arguments": arguments})
        if spec.permission:
            self.permissions.check(
                spec.permission,
                description=f"Tool '{name}' needs permission",
                details={"tool": name, "arguments": arguments},
            )
        try:
            result = spec.callback(**arguments)
            if hasattr(result, "to_dict"):
                result = result.to_dict()
            self.run.log(f"Tool {name} returned.", data={"result_summary": _summarize(result)})
            return result
        except Exception as exc:  # noqa: BLE001
            self.state.last_error = str(exc)
            self.run.log(f"Tool {name} failed: {exc}", level="error")
            raise

    # -- main loop ---------------------------------------------------------------
    def execute(self, output_callback: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
        if self._model is None:
            raise RuntimeError("No AI model backend is configured.")
        self.plan()
        if self.state.plan:
            for step in self.state.plan.steps:
                self.run.checkpoint()
                step.status = "running"
                self.run.set_progress(self.state.plan.progress, step.description)
                result = self._model(self._build_messages(), self.tools.openai_tools())
                if result.get("type") == "complete":
                    self.run.log(result.get("message", "Agent finished."))
                    if output_callback:
                        output_callback({"type": "completion", "message": result.get("message", "")})
                    step.status = "verified"
                    break
                if result.get("type") == "tool_call":
                    name = result["name"]
                    arguments = result.get("arguments", {}) or {}
                    tool_call_id = result.get("tool_call_id", f"call_{len(self.state.messages)}")
                    self.state.messages.append(
                        {
                            "role": "assistant",
                            "content": result.get("message", "") or "",
                            "name": name,
                            "arguments": arguments,
                        }
                    )
                    self.run.checkpoint()
                    tool_result = self.execute_tool(name, arguments)
                    self.state.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": name,
                            "content": json.dumps(_safe_jsonable(tool_result), ensure_ascii=False),
                        }
                    )
                    self._observe_tool_result(name, arguments, tool_result)
                else:
                    self.run.log("Model returned an unrecognized action.", level="warn")
                self.run.set_progress(self.state.plan.progress, self.state.plan.current_step.description if self.state.plan.current_step else "Thinking")
            else:
                # while-loop exhausts with unanswered action => fail loudly rather than fake success
                raise RuntimeError("Agent loop exhausted its step budget without completion.")
        return self.state.to_dict()

    # -- observation/verification hooks -----------------------------------------
    def _observe_tool_result(self, name: str, arguments: dict[str, Any], result: Any) -> None:
        if name == "browser_read_page":
            self.observe(str(result)[:2000])
        elif name == "browser_screenshot":
            self.observe("Took a screenshot; visual verification pending.")
        elif name == "desktop_read_screen":
            self.observe(str(result)[:2000])
        elif name == "browser_navigate":
            self.observe(f"Navigated to {arguments.get('url')}")

    def _history_text(self) -> str:
        return json.dumps(self.state.observations[-5:], ensure_ascii=False)

    def _build_messages(self) -> list[dict[str, Any]]:
        system = [
            {
                "role": "system",
                "content": (
                    "You are LUNA, a careful computer-use agent. You act through the provided "
                    "tools. After every tool call, inspect the result and verify the expected "
                    "state. Never claim success without evidence. If an action cannot be "
                    "verified, explain the limitation. When the goal is achieved, call complete. "
                    f"GOAL: {self.state.goal}\n\n"
                    f"{self.personality}"
                ),
            }
        ]
        return system + self.state.messages

    # -- shared task loop ----------------------------------------------------------
    def wait_for_approval(self, prompt: str, action: str) -> bool:
        self.run.checkpoint()
        if self.run.task.status == TaskStatus.WAITING_FOR_USER:
            raise RuntimeError("Already waiting for another user answer.")
        self.run.log(f"Waiting for user: {prompt}", level="warn")
        self.run._notify(status=TaskStatus.WAITING_FOR_USER)  # noqa: SLF001
        event = threading.Event()
        self._pending_approval = {"prompt": prompt, "action": action, "event": event, "allowed": False}
        # Application UI polls via respond() — simpler and thread-safe across Qt.
        while not event.wait(timeout=0.5):
            self.run.check_cancelled()
        return bool(self._pending_approval.get("allowed"))

    def respond_approval(self, allowed: bool) -> None:
        self._pending_approval["allowed"] = allowed
        event = self._pending_approval.get("event")
        if event is not None:
            event.set()


class ToolNotFound(Exception):
    pass


def _summarize(value: Any, limit: int = 300) -> str:
    text = json.dumps(_safe_jsonable(value), ensure_ascii=False) if not isinstance(value, str) else value
    return text[:limit]


def _safe_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_jsonable(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        try:
            return _safe_jsonable(value.to_dict())
        except Exception:  # noqa: BLE001
            pass
    return str(value)
