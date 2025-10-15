import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import case_documentation_app as app


class FakeSessionState(dict):
    """Simple dictionary-backed object exposing attribute access."""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


@pytest.fixture
def fake_state(monkeypatch, tmp_path):
    state = FakeSessionState()
    state.case = {}
    state._autosave_loaded = False
    state.autosave_notice = None

    autosave_path = tmp_path / "autosave.json"
    monkeypatch.setattr(app, "AUTOSAVE_FILE", str(autosave_path))
    monkeypatch.setattr(app.st, "session_state", state, raising=False)

    return state, autosave_path


class CustomPayload:
    def __init__(self, title=None, notes=None):
        self.title = title
        self.notes = notes


def test_load_autosave_with_valid_file(fake_state):
    state, autosave_path = fake_state
    payload = {"case": {"number": 1}}
    autosave_path.write_text(json.dumps(payload), encoding="utf-8")

    app.load_autosave()

    assert state.case == payload["case"]
    assert state._autosave_loaded is True


@pytest.mark.parametrize(
    "description, setup_file",
    [
        ("corrupted json", lambda path: path.write_text("{not-json}", encoding="utf-8")),
        ("missing file", lambda path: None),
    ],
)
def test_load_autosave_handles_invalid_inputs(description, setup_file, fake_state):
    state, autosave_path = fake_state
    setup_file(autosave_path)

    app.load_autosave()

    assert state.case == {}
    assert state._autosave_loaded is True


@pytest.mark.parametrize(
    "payload, expected_notes",
    [
        ({"title": "", "notes": "Investigation", "created_at": "", "updated_at": None}, "Investigation"),
        ("Quick remote", "Quick remote"),
        (CustomPayload(title="Custom", notes=""), ""),
    ],
)
def test_normalize_remote_session_list_sanitizes_entries(payload, expected_notes):
    normalized = app._normalize_remote_session_list([payload])

    assert len(normalized) == 1
    entry = normalized[0]

    assert isinstance(entry, app.RemoteSessionEntry)
    assert entry.title.strip() != ""
    assert entry.created_at
    assert entry.updated_at
    assert entry.notes == expected_notes


def test_tail_log_reads_last_lines(tmp_path):
    log_path = tmp_path / "application.log"
    log_path.write_text("""line1\nline2\nline3\n""", encoding="utf-8")

    result = app.tail_log(log_path, lines=2)

    assert result == "line2\nline3\n"


def test_tail_log_missing_file_returns_friendly_message(tmp_path):
    missing_path = tmp_path / "missing.log"

    result = app.tail_log(missing_path)

    assert result == "Log file not found."


def test_tail_log_unreadable_file_reports_error(tmp_path, monkeypatch):
    log_path = tmp_path / "unreadable.log"
    log_path.write_text("content", encoding="utf-8")

    original_open = Path.open

    def failing_open(self, *args, **kwargs):
        if self == log_path:
            raise OSError("boom")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)

    result = app.tail_log(log_path)

    assert result == "Unable to read log file: boom"
