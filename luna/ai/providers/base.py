"""AI provider interface. LUNA is not tied to a single provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class ProviderInfo:
    name: str
    display_name: str
    local: bool
    supports_tools: bool
    supports_streaming: bool


@dataclass
class LLMResult:
    content: str
    tool_call: dict[str, Any] | None = None
    finish_reason: str = "stop"
    raw: dict[str, Any] | None = None


class AIProvider(ABC):
    """Minimal chat interface used by the agent."""

    info: ProviderInfo

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResult:
        ...

    def stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> Iterable[str]:
        raise NotImplementedError("This provider does not support streaming.")

    def close(self) -> None:  # pragma: no cover
        return None
