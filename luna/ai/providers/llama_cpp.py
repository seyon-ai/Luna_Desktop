"""llama-cpp-python local inference provider (optional dependency)."""

from __future__ import annotations

import json
from typing import Any

from luna.ai.providers.base import AIProvider, LLMResult, ProviderInfo


class LlamaCppProvider(AIProvider):
    info = ProviderInfo("llama_cpp", "llama.cpp (local GGUF)", local=True, supports_tools=False, supports_streaming=True)

    def __init__(self, model_path: str, n_ctx: int = 8192, n_gpu_layers: int = -1) -> None:
        try:
            from llama_cpp import Llama  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "llama-cpp-python is not installed. Install with: pip install llama-cpp-python"
            ) from exc
        self._llama = Llama(model_path=model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
        self.model_path = model_path
        self.n_ctx = n_ctx

    def chat(self, messages, tools=None, **kwargs):
        if tools:
            raise RuntimeError("Tool calling is not supported by the raw llama.cpp provider; use Ollama.")
        output = self._llama.create_chat_completion(messages=messages, temperature=kwargs.get("temperature", 0.3))
        text = output["choices"][0]["message"].get("content", "")
        return LLMResult(content=text, raw=output)

    def stream(self, messages, **kwargs):
        for chunk in self._llama.create_chat_completion(messages=messages, stream=True):
            token = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if token:
                yield token
