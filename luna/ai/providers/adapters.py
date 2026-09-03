"""Adapter between provider LLMResult and the agent's normalized action dict."""

from __future__ import annotations

from typing import Any

from luna.ai.providers.base import AIProvider, LLMResult


def agent_chat(provider: AIProvider):
    """Return a callable(messages, tools) -> agent action dict."""

    def call(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        result: LLMResult = provider.chat(messages, tools=tools)
        if result.tool_call:
            return {
                "type": "tool_call",
                "name": result.tool_call.get("name", ""),
                "arguments": result.tool_call.get("arguments", {}) or {},
                "tool_call_id": result.tool_call.get("tool_call_id", ""),
                "message": result.content,
            }
        return {"type": "complete", "message": result.content or "Done."}

    return call
