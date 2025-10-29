from __future__ import annotations

import sys
import types

import pytest

from KiroshiApp.core.ai_client import AIClient
from KiroshiApp.core.model import CaseData, RemoteSessionEntry


def _make_case(**overrides: object) -> CaseData:
    data = {
        "company_name": "Acme Dental",
        "case_id": "CASE-100",
        "brief_description": "Scanner disconnected",
        "description": "The scanner intermittently disconnects during capture.",
        "solution": "Updated firmware",
        "additional_info": "Follow up tomorrow",
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


def test_local_api_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"completion": "Local API response"}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return payload

    def _fake_post(url: str, json: dict[str, object], timeout: int) -> DummyResponse:
        assert url == "https://local-api"
        assert json["prompt"] == "Hello"
        assert timeout == 30
        return DummyResponse()

    monkeypatch.setattr("KiroshiApp.core.ai_client.requests.post", _fake_post)
    client = AIClient(mode="local_api", base_url="https://local-api")
    response = client.invoke_completion("Hello")
    assert response == payload["completion"]


def test_cloud_mode_uses_openai(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert calls["input"] == "Prompt"
    assert calls["max_output_tokens"] == 64
    assert calls["api_key"] == "secret"


def test_local_model_mode(monkeypatch: pytest.MonkeyPatch) -> None:
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

    assert text == "Prompt :: 32"
