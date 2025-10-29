"""AI client placeholder for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AISettings:
    """Minimal configuration container for AI integrations."""

    provider: str = "disabled"
    model: str = ""


class AIClient:
    """Stub AI client that echoes a canned response."""

    def __init__(self, settings: AISettings | None = None) -> None:
        self._settings = settings or AISettings()

    def invoke_completion(self, prompt: str) -> str:
        """Return a placeholder completion string."""
        return f"[AI disabled] Prompt received: {prompt}" if prompt else "[AI disabled]"
