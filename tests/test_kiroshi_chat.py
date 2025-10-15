"""Unit tests for the Kiroshi chat helpers."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import kiroshi_chat


@pytest.fixture(autouse=True)
def fake_streamlit_state(monkeypatch, tmp_path: Path):
    """Provide a dict-backed Streamlit session state and tmp storage."""

    session_state: dict[str, object] = {}
    fake_st = types.SimpleNamespace(session_state=session_state)
    monkeypatch.setattr(kiroshi_chat, "st", fake_st)

    memory_file = tmp_path / "memory.json"
    manual_file = tmp_path / "manual.json"
    reference_file = tmp_path / "reference.json"

    monkeypatch.setattr(kiroshi_chat, "MEMORY_FILE", str(memory_file))
    monkeypatch.setattr(kiroshi_chat, "MANUAL_DOCS_FILE", str(manual_file))
    monkeypatch.setattr(kiroshi_chat, "KIROSHI_REFERENCE_FILE", reference_file)

    yield session_state


def test_load_memory_defaults_when_missing(fake_streamlit_state):
    history = kiroshi_chat.load_memory()

    assert history == []
    assert fake_streamlit_state["system_prompt"] == kiroshi_chat.SYSTEM_PROMPT
    assert fake_streamlit_state["personality_mode"] == "utility"
    assert fake_streamlit_state["kiroshi_sarcasm_mode"] is False
    assert fake_streamlit_state["assistant_notes"] == []


def test_load_memory_defaults_when_corrupted(tmp_path: Path, fake_streamlit_state):
    Path(kiroshi_chat.MEMORY_FILE).write_text("{not valid", encoding="utf-8")

    history = kiroshi_chat.load_memory()

    assert history == []
    assert fake_streamlit_state["system_prompt"] == kiroshi_chat.SYSTEM_PROMPT
    assert fake_streamlit_state["personality_mode"] == "utility"
    assert fake_streamlit_state["kiroshi_sarcasm_mode"] is False
    assert fake_streamlit_state["assistant_notes"] == []


def test_load_memory_respects_saved_values(fake_streamlit_state):
    saved_payload = {
        "history": [{"role": "user", "content": "hey"}],
        "system_prompt": "Prompt {personality_mode}",
        "personality_mode": "coffee",
        "kiroshi_sarcasm_mode": True,
        "assistant_notes": [
            {
                "id": "note-1",
                "text": "  follow-up with tier 2  ",
                "supervisor": " Ops  ",
                "created_at": "2024-01-01  ",
                "areas": [" escalations ", "escalations", ""],
            },
            "ignore",
            {"text": ""},
        ],
    }
    Path(kiroshi_chat.MEMORY_FILE).write_text(
        json.dumps(saved_payload), encoding="utf-8"
    )

    history = kiroshi_chat.load_memory()

    assert history == saved_payload["history"]
    assert fake_streamlit_state["system_prompt"] == "Prompt {personality_mode}"
    assert fake_streamlit_state["personality_mode"] == "coffee"
    assert fake_streamlit_state["kiroshi_sarcasm_mode"] is True
    assert fake_streamlit_state["assistant_notes"] == [
        {
            "id": "note-1",
            "text": "follow-up with tier 2",
            "supervisor": "Ops",
            "created_at": "2024-01-01",
            "areas": ["escalations"],
        }
    ]


def test_save_memory_round_trip(fake_streamlit_state):
    fake_streamlit_state["system_prompt"] = "Prompt {personality_mode}"
    fake_streamlit_state["personality_mode"] = "coffee"
    fake_streamlit_state["kiroshi_sarcasm_mode"] = True
    fake_streamlit_state["assistant_notes"] = [
        {
            "id": "abc",
            "text": "  be concise ",
            "supervisor": " QA  ",
            "areas": [" tone ", "tone"],
        },
        {"text": ""},
    ]

    history = [{"role": "user", "content": "Hello"}]
    kiroshi_chat.save_memory(history)

    stored = json.loads(Path(kiroshi_chat.MEMORY_FILE).read_text(encoding="utf-8"))
    assert stored["history"] == history
    assert stored["system_prompt"] == "Prompt {personality_mode}"
    assert stored["personality_mode"] == "coffee"
    assert stored["kiroshi_sarcasm_mode"] is True
    assert stored["assistant_notes"] == [
        {
            "id": "abc",
            "text": "be concise",
            "supervisor": "QA",
            "created_at": "",
            "areas": ["tone"],
        }
    ]

    fake_streamlit_state.clear()
    history_from_disk = kiroshi_chat.load_memory()
    assert history_from_disk == history
    assert fake_streamlit_state["assistant_notes"] == stored["assistant_notes"]
    assert fake_streamlit_state["personality_mode"] == "coffee"
    assert fake_streamlit_state["kiroshi_sarcasm_mode"] is True


def test_persist_sarcasm_preference_writes_to_disk(fake_streamlit_state):
    fake_streamlit_state["system_prompt"] = "Prompt {personality_mode}"
    fake_streamlit_state["personality_mode"] = "utility"
    fake_streamlit_state["kiroshi_sarcasm_mode"] = True
    fake_streamlit_state["assistant_notes"] = []
    fake_streamlit_state["kiroshi_chat_history"] = []

    kiroshi_chat._persist_sarcasm_preference()

    stored = json.loads(Path(kiroshi_chat.MEMORY_FILE).read_text(encoding="utf-8"))
    assert stored["kiroshi_sarcasm_mode"] is True


def test_load_manual_docs_and_search(tmp_path: Path, fake_streamlit_state):
    manual_payload = [
        {"title": "Alpha", "content": "Manual guidance"},
        {"title": "", "content": "ignored"},
        "skip",
    ]
    Path(kiroshi_chat.MANUAL_DOCS_FILE).write_text(
        json.dumps(manual_payload), encoding="utf-8"
    )

    quick_reference = [
        {"title": "Beta", "content": "Quick ref"},
        {"title": " Alpha ", "content": "Duplicate should be skipped"},
        "discard",
    ]
    kiroshi_chat.KIROSHI_REFERENCE_FILE.write_text(
        json.dumps(quick_reference), encoding="utf-8"
    )

    docs = kiroshi_chat.load_manual_docs()

    assert docs[0] == {"title": "Alpha", "content": "Manual guidance"}
    assert docs[1] == {"title": "", "content": "ignored"}
    assert docs[2] == {"title": "Beta", "content": "Quick ref"}

    assert kiroshi_chat.search_manual_docs("beta", docs) == [
        {"title": "Beta", "content": "Quick ref"}
    ]
    assert kiroshi_chat.search_manual_docs("manual", docs) == [
        {"title": "Alpha", "content": "Manual guidance"}
    ]


def test_build_system_prompt_directives(fake_streamlit_state):
    fake_streamlit_state["system_prompt"] = "Base {personality_mode}"
    fake_streamlit_state["personality_mode"] = "coffee"
    fake_streamlit_state["kiroshi_sarcasm_mode"] = True

    sarcastic_prompt = kiroshi_chat.build_system_prompt()
    assert "Base coffee" in sarcastic_prompt
    assert "dry, sarcastic tone" in sarcastic_prompt

    fake_streamlit_state["kiroshi_sarcasm_mode"] = False
    supportive_prompt = kiroshi_chat.build_system_prompt()
    assert "Base coffee" in supportive_prompt
    assert "supportive tone" in supportive_prompt


def test_query_kiroshi_attaches_memory_prompt(monkeypatch, fake_streamlit_state):
    fake_streamlit_state["system_prompt"] = "Prompt {personality_mode}"
    fake_streamlit_state["personality_mode"] = "utility"
    fake_streamlit_state["kiroshi_sarcasm_mode"] = False

    monkeypatch.setattr(
        kiroshi_chat,
        "build_assistant_memory_prompt",
        lambda: "Remember the supervisor notes.",
    )

    captured: dict[str, object] = {}

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": " final reply "}}]}

    def fake_post(url, headers, json, timeout, verify):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return DummyResponse()

    monkeypatch.setattr(kiroshi_chat.requests, "post", fake_post)

    reply = kiroshi_chat.query_kiroshi(
        "User input",
        [{"role": "assistant", "content": "Hello again"}],
        api_key="token",
        model="gpt-4",
        base_url="https://example.com",
    )

    assert reply == "final reply"

    assert captured["url"] == "https://example.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer token"

    messages = captured["json"]["messages"]
    assert messages[0]["role"] == "system"
    assert "supportive tone" in messages[0]["content"]
    assert messages[1] == {"role": "system", "content": "Remember the supervisor notes."}
    assert messages[2] == {"role": "assistant", "content": "Hello again"}
    assert messages[3] == {"role": "user", "content": "User input"}


def test_query_kiroshi_skips_empty_memory_prompt(monkeypatch, fake_streamlit_state):
    fake_streamlit_state["system_prompt"] = "Prompt {personality_mode}"
    fake_streamlit_state["personality_mode"] = "utility"
    fake_streamlit_state["kiroshi_sarcasm_mode"] = False

    monkeypatch.setattr(kiroshi_chat, "build_assistant_memory_prompt", lambda: None)

    class DummyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": " ok "}}]}

    captured_messages: list[dict[str, str]] = []

    def fake_post(url, headers, json, timeout, verify):
        captured_messages.extend(json["messages"])
        return DummyResponse()

    monkeypatch.setattr(kiroshi_chat.requests, "post", fake_post)

    reply = kiroshi_chat.query_kiroshi(
        "Test", [], api_key=None, model="gpt-4", base_url="https://example.com"
    )

    assert reply == "ok"
    assert len(captured_messages) == 2  # only system prompt + user message
    assert captured_messages[0]["role"] == "system"
    assert captured_messages[1] == {"role": "user", "content": "Test"}
