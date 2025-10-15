import uuid

import pytest
import streamlit as st

from kiroshi_chat import (
    build_assistant_memory_prompt,
    get_assistant_notes,
    set_assistant_notes,
)


@pytest.fixture(autouse=True)
def reset_session_state():
    """Ensure Streamlit's session state is isolated across tests."""

    st.session_state.clear()
    yield
    st.session_state.clear()


@pytest.fixture
def messy_notes_payload():
    duplicated_id = uuid.uuid4().hex
    return [
        {
            "id": duplicated_id,
            "text": "  Keep responses sharp  ",
            "supervisor": "  Alice  ",
            "areas": ["AI Assistance", "AI Assistance", "Quick Actions", "  "],
            "created_at": " 2024-01-01T00:00:00Z ",
        },
        {
            "id": uuid.uuid4().hex,
            "text": "   ",
            "supervisor": "Ignored",
        },
        {
            "text": "Use bullet points",
            "supervisor": "Bob",
            "areas": ["Kiroshi Chat", "  Kiroshi Chat  ", "Quick Actions"],
        },
        "not-a-mapping",
    ]


def test_set_and_get_assistant_notes_sanitizes_entries(messy_notes_payload):
    sanitized = set_assistant_notes(messy_notes_payload)

    assert len(sanitized) == 2
    assert st.session_state["assistant_notes"] == sanitized

    first, second = sanitized
    assert first["text"] == "Keep responses sharp"
    assert first["supervisor"] == "Alice"
    assert first["created_at"] == "2024-01-01T00:00:00Z"
    assert first["areas"] == ["AI Assistance", "Quick Actions"]

    assert second["text"] == "Use bullet points"
    assert second["supervisor"] == "Bob"
    assert second["areas"] == ["Kiroshi Chat", "Quick Actions"]

    retrieved = get_assistant_notes()
    assert retrieved == sanitized


def test_set_assistant_notes_resets_session_state():
    set_assistant_notes([
        {"text": "Keep it brief", "areas": ["Kiroshi Chat"]},
    ])
    assert get_assistant_notes()

    cleared = set_assistant_notes([])
    assert cleared == []
    assert get_assistant_notes() == []
    assert st.session_state["assistant_notes"] == []


def test_build_assistant_memory_prompt_formats_bullets(messy_notes_payload):
    set_assistant_notes(messy_notes_payload)

    prompt = build_assistant_memory_prompt()
    assert prompt is not None

    lines = prompt.splitlines()
    assert lines[0].startswith("Persistent supervisor calibration reminders")
    bullet_lines = [line for line in lines[1:] if line.startswith("-")]
    assert len(bullet_lines) == 2

    assert "- Keep responses sharp (focus: AI Assistance, Quick Actions; source: Alice)" in bullet_lines
    assert "- Use bullet points (focus: Kiroshi Chat, Quick Actions; source: Bob)" in bullet_lines
