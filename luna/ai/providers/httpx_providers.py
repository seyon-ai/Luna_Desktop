"""HTTP providers: Ollama (default local) and OpenAI-compatible APIs."""

from __future__ import annotations

import json
from typing import Any, Iterable

from luna.ai.providers.base import AIProvider, LLMResult, ProviderInfo

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


class OllamaProvider(AIProvider):
    """Local Ollama provider (default). No API keys, fully local inference."""

    info = ProviderInfo("ollama", "Ollama (local)", local=True, supports_tools=True, supports_streaming=True)

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "", timeout: float = 120.0) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required for the Ollama provider. Install with: pip install httpx")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages, tools=None, **kwargs):
        payload: dict[str, Any] = {
            "model": self.model or "llama3.2",
            "messages": messages,
            "stream": False,
            "options": {"temperature": kwargs.get("temperature", 0.3)},
        }
        if tools:
            payload["tools"] = tools
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        tool_call = _extract_ollama_tool(data)
        return LLMResult(
            content=data.get("message", {}).get("content", ""),
            tool_call=tool_call,
            finish_reason=str(data.get("done_reason", "stop")),
            raw=data,
        )

    def stream(self, messages, **kwargs):
        payload = {"model": self.model or "llama3.2", "messages": messages, "stream": True}
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break


class OpenAICompatibleProvider(AIProvider):
    """OpenAI-compatible chat completions API (local servers or managed APIs).

    API keys are read from an environment variable named in settings; they are
    never stored in source code or committed.
    """

    info = ProviderInfo(
        "openai_compatible", "OpenAI-compatible API", local=False, supports_tools=True, supports_streaming=True
    )

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        temperature: float = 0.3,
    ) -> None:
        if httpx is None:
            raise RuntimeError("httpx is required.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(self, messages, tools=None, **kwargs):
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        message = data["choices"][0]["message"]
        content = message.get("content", "") or ""
        tool_call = None
        calls = message.get("tool_calls") or []
        if calls:
            call = calls[0]
            fn = call.get("function", {})
            args = fn.get("arguments") or "{}"
            try:
                args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                args = {"_raw": args}
            tool_call = {
                "type": "tool_call",
                "name": fn.get("name", ""),
                "arguments": args,
                "tool_call_id": call.get("id", ""),
            }
        return LLMResult(
            content=content,
            tool_call=tool_call,
            finish_reason=str(data["choices"][0].get("finish_reason", "stop")),
            raw=data,
        )

    def stream(self, messages, **kwargs):
        payload = {"model": self.model, "messages": messages, "stream": True}
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers()) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    data = json.loads(chunk)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token


def _extract_ollama_tool(data: dict[str, Any]) -> dict[str, Any] | None:
    message = data.get("message", {}) or {}
    calls = message.get("tool_calls") or []
    if not calls:
        return None
    call = calls[0]
    fn = call.get("function", {})
    return {
        "type": "tool_call",
        "name": fn.get("name", ""),
        "arguments": fn.get("arguments", {}) or {},
        "tool_call_id": call.get("id", ""),
    }
