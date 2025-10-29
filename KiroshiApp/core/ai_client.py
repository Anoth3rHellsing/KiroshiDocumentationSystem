"""Lightweight AI abstraction used by the experimental desktop client."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import requests

from .model import CaseData, format_remote_sessions_summary

LOGGER = logging.getLogger(__name__)
AIMode = Literal["cloud", "local_api", "local_model"]


@dataclass
class AIClient:
    """Dispatch completion requests to different AI backends."""

    mode: AIMode = "cloud"
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 30
    local_model: str | None = None
    _local_pipeline: Any = field(default=None, init=False, repr=False)

    def invoke_completion(self, prompt: str, **kwargs: Any) -> str:
        """Send ``prompt`` to the configured backend and return the response text."""

        LOGGER.debug("Invoking completion using mode=%s", self.mode)
        if self.mode == "cloud":
            return self._invoke_cloud(prompt, **kwargs)
        if self.mode == "local_api":
            return self._invoke_local_api(prompt, **kwargs)
        if self.mode == "local_model":
            return self._invoke_local_model(prompt, **kwargs)
        raise ValueError(f"Unsupported AI mode: {self.mode}")

    def generate_email_body(
        self,
        case: CaseData,
        *,
        tone: str = "formal",
        summary: str | None = None,
        audience: str = "customer",
        **kwargs: Any,
    ) -> str:
        """Produce an outbound email body describing ``case``."""

        summary = summary or case.brief_description or case.description
        troubleshooting = format_remote_sessions_summary(case.remote_sessions)
        if not troubleshooting:
            troubleshooting = case.remote_steps

        prompt = f"""
You are assisting a support engineer preparing a follow-up email for a resolved case.
Tone: {tone}
Audience: {audience}
Case ID: {case.case_id}
Company: {case.company_name}
Caller: {case.caller_name}
Summary: {summary}
Solution: {case.solution}
Next Steps: {case.additional_info}
Troubleshooting notes:
{troubleshooting}
""".strip()
        return self.invoke_completion(prompt, **kwargs)

    # Backends -----------------------------------------------------------------
    def _invoke_cloud(self, prompt: str, **kwargs: Any) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "openai package is required for cloud mode"
            ) from exc

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        options = dict(kwargs)
        if "max_tokens" in options and "max_output_tokens" not in options:
            options["max_output_tokens"] = options.pop("max_tokens")
        response = client.responses.create(model=self.model, input=prompt, **options)
        text = getattr(response, "output_text", None)
        if text is None:
            if hasattr(response, "choices"):
                text = response.choices[0].message.content  # type: ignore[attr-defined]
            else:
                text = str(response)
        return text

    def _invoke_local_api(self, prompt: str, **kwargs: Any) -> str:
        if not self.base_url:
            raise RuntimeError("local_api mode requires a base_url")
        payload = {"prompt": prompt, **kwargs}
        resp = requests.post(self.base_url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        for key in ("completion", "text", "response"):
            if isinstance(data, dict) and key in data:
                return str(data[key])
        return str(data)

    def _invoke_local_model(self, prompt: str, **kwargs: Any) -> str:
        model_name = self.local_model or self.model
        try:
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "transformers package is required for local_model mode"
            ) from exc

        pipeline_model = None if self._local_pipeline is None else getattr(self._local_pipeline.model, "name_or_path", None)
        if self._local_pipeline is None or pipeline_model != model_name:
            LOGGER.info("Loading local transformers pipeline for %s", model_name)
            self._local_pipeline = pipeline(
                "text-generation",
                model=model_name,
            )
        generator = self._local_pipeline
        max_new_tokens = kwargs.get("max_tokens") or kwargs.get("max_new_tokens") or 256
        generated = generator(prompt, max_new_tokens=int(max_new_tokens))
        if isinstance(generated, list) and generated:
            first = generated[0]
            if isinstance(first, dict) and "generated_text" in first:
                return str(first["generated_text"]).strip()
        return str(generated)
