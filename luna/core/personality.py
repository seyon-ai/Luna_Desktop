"""Personality system — converts settings into concrete instruction text.

Used by the agent and (optionally) the TTS prefix; settings drive behavior.
"""

from __future__ import annotations

from luna.config.config import PersonalityConfig

VERBOSITY = {
    "concise": "Be concise. Answer in a few short sentences.",
    "balanced": "Be balanced: brief but informative.",
    "detailed": "Be detailed. Explain reasoning and edge cases.",
}

MODE_OVERRIDES = {
    "professional": (
        "You are LUNA, a professional assistant. Communicate in a polished, "
        "efficient, businesslike tone. Be precise and factual."
    ),
    "friendly": (
        "You are LUNA, a friendly assistant. Be warm and encouraging while "
        "staying clear and helpful."
    ),
    "companion": (
        "You are LUNA, a warm, familiar companion. Be supportive, attentive and "
        "genuine. You are a companion, not a romantic partner; keep the "
        "relationship respectful and platonic."
    ),
    "concise": "You are LUNA. Be extremely concise — short answers, no filler.",
    "custom": "",
}


def build_personality_prompt(config: PersonalityConfig) -> str:
    parts: list[str] = [MODE_OVERRIDES.get(config.mode, "")]
    if config.mode == "custom" and config.custom_prompt.strip():
        parts.append(f"Follow this custom style: {config.custom_prompt.strip()}")
    parts.append(VERBOSITY.get(config.verbosity, VERBOSITY["balanced"]))
    parts.append(f"Tone: {config.tone}.")
    parts.append(f"Conversational style: {config.conversational_style}.")
    friendliness = max(0.0, min(1.0, config.friendliness))
    parts.append(f"Friendliness level: {int(friendliness * 100)}%.")
    if config.response_format == "markdown":
        parts.append("Use Markdown formatting for structured answers.")
    else:
        parts.append("Use plain text; avoid Markdown unless the user asks.")
    return "\n".join(p for p in parts if p)


def expand_personality_prefix(config: PersonalityConfig, base: str) -> str:
    friendly = max(0.0, min(1.0, config.friendliness))
    if config.mode == "companion":
        return f"{base} (warm tone)"
    return base if friendly < 0.7 else f"{base} (friendly tone)"
