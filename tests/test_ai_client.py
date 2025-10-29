from __future__ import annotations

import sys
import types

import pytest

from KiroshiApp.core.ai_client import AIClient
from KiroshiApp.core.model import CaseData, RemoteSessionEntry


@pytest.fixture(autouse=True)
def fake_chat_memory(monkeypatch: pytest.MonkeyPatch):
    import KiroshiApp.core.ai_client as ai_module

    memory_store: list[dict[str, str]] = []
    session_state: dict[str, object] = {}

    ai_module.kiroshi_chat.st = types.SimpleNamespace(session_state=session_state)

    def _load_memory() -> list[dict[str, str]]:
        return list(memory_store)

    def _save_memory(history: list[dict[str, str]]) -> None:
        memory_store[:] = list(history)
        session_state["kiroshi_chat_history"] = list(history)

    def _build_prompt() -> str | None:
        notes = session_state.get("assistant_notes", [])
        lines: list[str] = []
        if isinstance(notes, list):
            for note in notes:
                if isinstance(note, dict):
                    text = str(note.get("text", "")).strip()
                    if text:
                        lines.append(text)
        return "\n".join(lines) if lines else None

    session_state["assistant_notes"] = []

    monkeypatch.setattr(ai_module.kiroshi_chat, "load_memory", _load_memory)
    monkeypatch.setattr(ai_module.kiroshi_chat, "save_memory", _save_memory)
    monkeypatch.setattr(ai_module.kiroshi_chat, "build_assistant_memory_prompt", _build_prompt)

    return memory_store, session_state


def _make_case(**overrides: object) -> CaseData:
    data = {
        "company_name": "Acme Dental",
        "case_id": "CASE-100",
        "brief_description": "Scanner disconnected",
        "description": "The scanner intermittently disconnects during capture.",
        "solution": "Updated firmware",
        "additional_info": "Follow up tomorrow",
        "phone_number": "555-0100",
        "contact_name": "Jamie Analyst",
        "email": "support@example.com",
        "remote_sessions": [
            RemoteSessionEntry(title="Diagnostics", notes="Reviewed USB stability"),
        ],
    }
    data.update(overrides)
    return CaseData(**data)


def test_generate_email_body_formats_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def _fake_invoke(prompt: str, **_: object) -> str:
        captured["prompt"] = prompt
        return "Generated body"

    client = AIClient()
    monkeypatch.setattr(client, "invoke_completion", _fake_invoke)

    case = _make_case()
    output = client.generate_email_body(case, tone="friendly", audience="customer")

    assert output == "Generated body"
    assert "Case ID: CASE-100" in captured["prompt"]
    assert "Reviewed USB stability" in captured["prompt"]
    assert "Tone: friendly" in captured["prompt"]


def test_local_api_mode(monkeypatch: pytest.MonkeyPatch, fake_chat_memory) -> None:
    payload = {"completion": "Local API response"}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return payload

    def _fake_post(url: str, json: dict[str, object], timeout: int) -> DummyResponse:
        assert url == "https://local-api"
        assert "Current request" in json["prompt"]
        assert "Hello" in json["prompt"]
        assert timeout == 30
        return DummyResponse()

    monkeypatch.setattr("KiroshiApp.core.ai_client.requests.post", _fake_post)
    client = AIClient(mode="local_api", base_url="https://local-api")
    response = client.invoke_completion("Hello")
    assert response == payload["completion"]
    memory_store, _ = fake_chat_memory
    assert memory_store[-2:] == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": payload["completion"]},
    ]


def test_cloud_mode_uses_openai(monkeypatch: pytest.MonkeyPatch, fake_chat_memory) -> None:
    calls: dict[str, object] = {}

    class DummyResponses:
        def create(self, *, model: str, input: str, **options: object) -> object:
            calls["model"] = model
            calls["input"] = input
            calls.update(options)

            class DummyResult:
                output_text = "Cloud text"

            return DummyResult()

    class DummyOpenAI:
        def __init__(self, api_key: str, base_url: str | None = None) -> None:
            calls["api_key"] = api_key
            calls["base_url"] = base_url
            self.responses = DummyResponses()

    dummy_module = types.SimpleNamespace(OpenAI=DummyOpenAI)
    monkeypatch.setitem(sys.modules, "openai", dummy_module)

    client = AIClient(mode="cloud", model="gpt-test", api_key="secret", base_url="https://api")
    text = client.invoke_completion("Prompt", max_tokens=64)

    assert text == "Cloud text"
    assert calls["model"] == "gpt-test"
    assert "Current request" in calls["input"]
    assert "Prompt" in calls["input"]
    assert calls["max_output_tokens"] == 64
    assert calls["api_key"] == "secret"


def test_local_model_mode(monkeypatch: pytest.MonkeyPatch, fake_chat_memory) -> None:
    class DummyGenerator:
        def __init__(self, model_name: str) -> None:
            self.model = types.SimpleNamespace(name_or_path=model_name)

        def __call__(self, prompt: str, max_new_tokens: int) -> list[dict[str, str]]:
            return [{"generated_text": f"{prompt} :: {max_new_tokens}"}]

    def _pipeline(task: str, model: str) -> DummyGenerator:
        assert task == "text-generation"
        return DummyGenerator(model)

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=_pipeline))

    client = AIClient(mode="local_model", local_model="tiny-model")
    text = client.invoke_completion("Prompt", max_tokens=32)

    assert "Prompt :: 32" in text
    history, _ = fake_chat_memory
    assert history[-2]["role"] == "user"
    assert "Prompt" in history[-2]["content"]
    assert history[-1]["role"] == "assistant"


def test_verify_case_data_flags_missing_fields(fake_chat_memory) -> None:
    client = AIClient()
    case = _make_case(company_name="", remote_sessions=[], solution="")
    missing = client.verify_case_data(case)
    fields = {entry["field"] for entry in missing}
    assert "company_name" in fields
    assert "solution" in fields


def test_set_personality_mode_updates_session_state(fake_chat_memory) -> None:
    _, session_state = fake_chat_memory
    client = AIClient()
    client.set_personality_mode("Sarcasm")
    assert client.get_personality_mode() == "sarcasm"
    assert session_state["kiroshi_sarcasm_mode"] is True
    assert session_state["personality_mode"] == "coffee"


def test_invoke_completion_tracks_memory(monkeypatch: pytest.MonkeyPatch, fake_chat_memory) -> None:
    memory_store, _ = fake_chat_memory
    client = AIClient(mode="local_api", base_url="https://local-api")

    def _fake_local(prompt: str, **_: object) -> str:
        assert "Current request" in prompt
        return "Respuesta"

    monkeypatch.setattr(client, "_invoke_local_api", _fake_local)
    text = client.invoke_completion("Hola")

    assert text == "Respuesta"
    assert memory_store[-2:] == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Respuesta"},
    ]
