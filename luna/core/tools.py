"""Tool registry: a declarative catalog of agent-callable tools with schemas."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    callback: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    permission: str | None = None  # e.g. "run_command"; None = always allowed
    category: str = "general"

    def to_openai(self) -> dict[str, Any]:
        properties = {
            name: {k: v for k, v in p.items() if k != "permission"}
            for name, p in self.parameters.items()
        }
        required = [n for n, p in self.parameters.items() if p.get("required")]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def add(
        self,
        name: str,
        description: str,
        callback: Callable[..., Any],
        parameters: dict[str, Any] | None = None,
        permission: str | None = None,
        category: str = "general",
    ) -> None:
        params = parameters or {}
        # infer required/type from signature defaults for convenience
        sig = inspect.signature(callback)
        infer = {}
        for pname, param in sig.parameters.items():
            if pname in ("ctx", "context", "tool_context"):
                continue
            infer[pname] = {
                "type": "string",
                "description": "",
                "required": param.default is inspect.Parameter.empty,
            }
        merged = {**infer, **{k: v for k, v in params.items()}}
        self.register(
            ToolSpec(
                name=name,
                description=description,
                callback=callback,
                parameters=merged,
                permission=permission,
                category=category,
            )
        )

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        return sorted(self._tools.values(), key=lambda t: t.name)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [t.to_openai() for t in self.all()]
