"""AI client helpers for the experimental desktop prototype."""
from __future__ import annotations

from collections.abc import MutableMapping, Sequence
import inspect
import types
from dataclasses import dataclass, fields
from importlib import import_module, util
from typing import Any, Callable

import requests

import kiroshi_chat
from .model import CaseData


_streamlit_exists: Callable[[], bool] | None = None
_streamlit_runtime_spec = util.find_spec("streamlit.runtime")
if _streamlit_runtime_spec is not None:
    _streamlit_runtime = import_module("streamlit.runtime")
    _streamlit_exists = getattr(_streamlit_runtime, "exists", None)


def _has_streamlit_context() -> bool:
    if _streamlit_exists is None:
        return False
    try:
        return bool(_streamlit_exists())
    except Exception:
        return False


@dataclass
class AISettings:
    """Minimal configuration container for AI integrations."""

    provider: str = "disabled"
    model: str = ""


class AIClient:
    """Backwards-compatible AI client used across the desktop tests."""

    _MEMORY_WINDOW = 8

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
        self._session_state = self._ensure_session_state()
        self._memory_history = self._load_memory_history()
        self._personality_mode = self._derive_personality_mode()

    def invoke_completion(self, prompt: str, **options: Any) -> str:
        """Dispatch a completion request based on the configured mode."""

        if not prompt:
            return ""

        enriched_prompt = self._build_contextual_prompt(prompt)

        if self.mode == "local_api":
            response = self._invoke_local_api(enriched_prompt, **options)
        elif self.mode == "cloud":
            response = self._invoke_cloud_api(enriched_prompt, **options)
        elif self.mode == "local_model":
            response = self._invoke_local_model(enriched_prompt, **options)
        else:
            response = (
                f"[AI disabled] Prompt received: {prompt}" if prompt else "[AI disabled]"
            )

        if self.mode in {"local_api", "cloud", "local_model"} and response:
            self._record_interaction(prompt, response)

        return response

    # ───────────────────── Personality & memory helpers ────────
    def _ensure_session_state(self) -> MutableMapping[str, object]:
        state = getattr(kiroshi_chat, "st", None)
        if state is not None:
            session_state: MutableMapping[str, object] | None = None
            if _has_streamlit_context():
                candidate = getattr(state, "session_state", None)
                if isinstance(candidate, MutableMapping):
                    session_state = candidate
            elif not inspect.ismodule(state):
                candidate = getattr(state, "session_state", None)
                if isinstance(candidate, MutableMapping):
                    session_state = candidate
            if session_state is not None:
                session_state.setdefault("assistant_notes", [])
                return session_state

        proxy = getattr(kiroshi_chat, "_desktop_session_state", None)
        if not isinstance(proxy, MutableMapping):
            proxy = {}
            setattr(kiroshi_chat, "_desktop_session_state", proxy)
        proxy.setdefault("assistant_notes", [])
        if state is None:
            kiroshi_chat.st = types.SimpleNamespace(session_state=proxy)
        return proxy

    def _load_memory_history(self) -> list[dict[str, str]]:
        raw_history = kiroshi_chat.load_memory()
        history: list[dict[str, str]] = []
        if isinstance(raw_history, Sequence):
            for entry in raw_history:
                if not isinstance(entry, dict):
                    continue
                role = str(entry.get("role", "")).strip()
                content = str(entry.get("content", "")).strip()
                if not role or not content:
                    continue
                history.append({"role": role, "content": content})
        self._session_state["kiroshi_chat_history"] = list(history)
        return history

    def _derive_personality_mode(self) -> str:
        sarcasm_enabled = bool(self._session_state.get("kiroshi_sarcasm_mode"))
        return "sarcasm" if sarcasm_enabled else "comfort"

    def get_personality_mode(self) -> str:
        """Return the active personality mode."""

        return self._personality_mode

    def set_personality_mode(self, mode: str) -> None:
        """Update the personality mode and persist it to shared memory."""

        normalized = mode.lower().strip()
        if normalized not in {"sarcasm", "comfort"}:
            raise ValueError("mode must be either 'sarcasm' or 'comfort'")
        self._personality_mode = normalized
        self._session_state["kiroshi_sarcasm_mode"] = normalized == "sarcasm"
        self._session_state["personality_mode"] = "coffee" if normalized == "sarcasm" else "utility"
        self._persist_memory()

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Return a copy of the stored conversation history."""

        return list(self._memory_history)

    def reset_history(self) -> None:
        """Clear the stored conversation history for all surfaces."""

        self._memory_history.clear()
        self._session_state["kiroshi_chat_history"] = []
        self._persist_memory()

    def _record_interaction(self, prompt: str, response: str) -> None:
        self._memory_history.append({"role": "user", "content": prompt})
        self._memory_history.append({"role": "assistant", "content": response})
        if len(self._memory_history) > self._MEMORY_WINDOW * 2:
            self._memory_history = self._memory_history[-self._MEMORY_WINDOW * 2 :]
        self._session_state["kiroshi_chat_history"] = list(self._memory_history)
        self._persist_memory()

    def _persist_memory(self) -> None:
        kiroshi_chat.save_memory(list(self._memory_history))

    def _build_contextual_prompt(self, prompt: str) -> str:
        lines = []
        if self._personality_mode == "sarcasm":
            lines.append(
                "Personality mode: Sarcasm. Reply with dry wit while remaining helpful and professional."
            )
        else:
            lines.append(
                "Personality mode: Comfort. Reply with a reassuring, patient tone while staying concise."
            )

        memory_prompt = kiroshi_chat.build_assistant_memory_prompt()
        if memory_prompt:
            lines.append("Supervisor reminders:\n" + memory_prompt)

        if self._memory_history:
            transcript = []
            for entry in self._memory_history[-self._MEMORY_WINDOW :]:
                speaker = "User" if entry.get("role") == "user" else "Assistant"
                transcript.append(f"{speaker}: {entry.get('content', '')}")
            lines.append("Recent exchange:\n" + "\n".join(transcript))

        lines.append("Current request:\n" + prompt)
        return "\n\n".join(lines)

    # ───────────────────── Case helpers ───────────────────────
    def verify_case_data(self, case: CaseData) -> list[dict[str, str]]:
        """Return a structured list of empty fields detected in ``case``."""

        missing: list[dict[str, str]] = []
        critical = {
            "company_name",
            "case_id",
            "brief_description",
            "description",
            "solution",
            "contact_name",
            "email",
            "phone_number",
        }

        for field in fields(CaseData):
            value = getattr(case, field.name)
            if isinstance(value, str):
                if value.strip():
                    continue
                severity = "critical" if field.name in critical else "info"
                missing.append(
                    {
                        "field": field.name,
                        "label": field.name.replace("_", " ").capitalize(),
                        "severity": severity,
                    }
                )
            elif isinstance(value, Sequence) and not isinstance(
                value, (str, bytes, bytearray)
            ):
                if value:
                    continue
                missing.append(
                    {
                        "field": field.name,
                        "label": field.name.replace("_", " ").capitalize(),
                        "severity": "info",
                    }
                )

        return missing

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
