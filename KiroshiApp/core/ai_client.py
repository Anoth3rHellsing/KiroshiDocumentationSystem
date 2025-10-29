"""AI client helpers for the experimental desktop prototype."""
from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any, Callable

import requests

from .model import CaseData


@dataclass
class AISettings:
    """Minimal configuration container for AI integrations."""

    provider: str = "disabled"
    model: str = ""


class AIClient:
    """Backwards-compatible AI client used across the desktop tests."""

    def __init__(
        self,
        *,
        mode: str = "disabled",
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        local_model: str | None = None,
        timeout: int = 30,
        settings: AISettings | None = None,
    ) -> None:
        self.mode = mode or (settings.provider if settings else "disabled")
        self.base_url = base_url
        self.model = model or (settings.model if settings else None)
        self.api_key = api_key
        self.local_model = local_model
        self.timeout = timeout
        self._settings = settings or AISettings(provider=self.mode, model=self.model or "")

    def invoke_completion(self, prompt: str, **options: Any) -> str:
        """Dispatch a completion request based on the configured mode."""

        if not prompt:
            return ""

        if self.mode == "local_api":
            return self._invoke_local_api(prompt, **options)
        if self.mode == "cloud":
            return self._invoke_cloud_api(prompt, **options)
        if self.mode == "local_model":
            return self._invoke_local_model(prompt, **options)
        return f"[AI disabled] Prompt received: {prompt}" if prompt else "[AI disabled]"

    # ───────────────────── Mode handlers ──────────────────────
    def _invoke_local_api(self, prompt: str, **options: Any) -> str:
        url = self.base_url or "http://127.0.0.1:8000"
        payload = {"prompt": prompt}
        payload.update({key: value for key, value in options.items() if value is not None})
        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("completion"), str):
            return data["completion"]
        return str(data)

    def _invoke_cloud_api(self, prompt: str, **options: Any) -> str:
        model = self.model or "gpt-3.5-turbo"
        max_tokens = options.get("max_tokens")
        client = self._get_openai_client()
        request_options = {"model": model, "input": prompt}
        if max_tokens is not None:
            request_options["max_output_tokens"] = max_tokens
        extra = {
            key: value
            for key, value in options.items()
            if key not in {"max_tokens"} and value is not None
        }
        request_options.update(extra)
        result = client.responses.create(**request_options)
        return getattr(result, "output_text", str(result))

    def _invoke_local_model(self, prompt: str, **options: Any) -> str:
        model_name = self.local_model or self.model or ""
        if not model_name:
            raise ValueError("local_model must be configured for local model mode")
        max_tokens = int(options.get("max_tokens", 256))
        pipeline = self._get_transformer_pipeline()
        generator = pipeline("text-generation", model=model_name)
        result = generator(prompt, max_new_tokens=max_tokens)
        if isinstance(result, list) and result and isinstance(result[0], dict):
            generated = result[0].get("generated_text")
            if isinstance(generated, str):
                return generated
        return str(result)

    def _get_openai_client(self) -> Any:
        module = self._import_module("openai")
        OpenAI = getattr(module, "OpenAI")
        return OpenAI(api_key=self.api_key or "", base_url=self.base_url)

    def _get_transformer_pipeline(self) -> Callable[..., Any]:
        module = self._import_module("transformers")
        return getattr(module, "pipeline")

    @staticmethod
    def _import_module(name: str) -> types.ModuleType:
        module = __import__(name)
        return module

    # ───────────────────── Helpers ────────────────────────────
    def generate_email_body(
        self,
        case: CaseData,
        *,
        tone: str = "neutral",
        audience: str = "customer",
    ) -> str:
        """Format a completion prompt for email generation."""

        troubleshooting_lines = []
        for entry in case.remote_sessions:
            summary = entry.notes.strip() or entry.title.strip()
            if summary:
                troubleshooting_lines.append(f"- {summary}")
        if case.solution:
            troubleshooting_lines.append(f"Solution: {case.solution}")
        if not troubleshooting_lines:
            troubleshooting_lines.append("- No remote sessions recorded")

        prompt = (
            "Compose a professional email update for the following support case.\n"
            f"Case ID: {case.case_id}\n"
            f"Company: {case.company_name}\n"
            f"Issue: {case.brief_description or case.description}\n"
            f"Troubleshooting summary:\n" + "\n".join(troubleshooting_lines) + "\n"
            f"Additional notes: {case.additional_info}\n"
            f"Tone: {tone}\n"
            f"Audience: {audience}"
        )
        return self.invoke_completion(prompt)
