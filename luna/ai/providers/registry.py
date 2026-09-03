"""Provider factory. Builds a provider from configuration, no keys in source."""

from __future__ import annotations

from typing import Any, cast

from luna.ai.providers.base import AIProvider
from luna.ai.providers.httpx_providers import OllamaProvider, OpenAICompatibleProvider
from luna.ai.providers.llama_cpp import LlamaCppProvider
from luna.config.config import ProviderConfig, SettingsManager

PROVIDER_NAMES = ("ollama", "openai_compatible", "llama_cpp")


def create_provider(config: ProviderConfig) -> AIProvider:
    name = config.provider
    if name == "ollama":
        return OllamaProvider(base_url=config.base_url, model=config.model, timeout=config.timeout_seconds)
    if name == "openai_compatible":
        api_key = SettingsManager.resolve_api_key(config.api_key_env)
        return OpenAICompatibleProvider(
            base_url=config.base_url,
            model=config.model,
            api_key=api_key,
            timeout=config.timeout_seconds,
            temperature=config.temperature,
        )
    if name == "llama_cpp":
        from luna.ai.model_manager.manager import ModelManager

        path = config.extra.get("model_path", "")
        if not path:
            raise ValueError("llama_cpp requires config.provider.extra.model_path")
        return LlamaCppProvider(model_path=str(path), n_ctx=int(config.extra.get("n_ctx", 8192)))
    raise ValueError(f"Unknown provider '{name}'. Choices: {', '.join(PROVIDER_NAMES)}")


def create_provider_from_settings(settings_manager: SettingsManager) -> AIProvider:
    return create_provider(settings_manager.settings.provider)
