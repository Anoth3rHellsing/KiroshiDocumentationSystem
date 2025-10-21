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


def test_update_case_remote_sessions_triggers_autosave(fake_state, monkeypatch):
    state, _ = fake_state
    case = app.CaseData(case_id="autosave-test")
    state.case = case
    app.D = case
    app.ensure_remote_session_entries(case)
    sessions = case.remote_sessions
    sessions[0].notes = "Documented troubleshooting"

    called = False

    def fake_autosave():
        nonlocal called
        called = True

    monkeypatch.setattr(app, "autosave", fake_autosave)

    app.update_case_remote_sessions(case, sessions)

    assert called is True


def test_auto_text_input_syncs_session_state_across_runs(fake_state, monkeypatch):
    state, _ = fake_state
    state.debug_mode = False
    app.CURRENT_CASE_IDX = 1
    app.D = app.CaseData()

    def fake_text_input(label, **kwargs):
        key = kwargs["key"]
        return state.get(key, kwargs.get("value", ""))

    monkeypatch.setattr(app.st, "text_input", fake_text_input)

    result = app.auto_text_input("Hardware test", "hardware_test")
    assert result == ""
    state_key = app.widget_state_key("hardware_test", app.CURRENT_CASE_IDX)
    assert state[state_key] == ""
    assert state[f"{state_key}__seed"] == ""
    assert app.D.hardware_test == ""

    state[state_key] = "Fan replaced"

    result = app.auto_text_input("Hardware test", "hardware_test")
    assert result == "Fan replaced"
    assert app.D.hardware_test == "Fan replaced"
    assert state[state_key] == "Fan replaced"
    assert state[f"{state_key}__seed"] == "Fan replaced"


def test_auto_text_area_refreshes_from_dataclass(fake_state, monkeypatch):
    state, _ = fake_state
    state.debug_mode = False
    app.CURRENT_CASE_IDX = 2
    app.D = app.CaseData()
    app.D.dell_benchmark_results = "Initial results"

    def fake_text_area(label, **kwargs):
        key = kwargs["key"]
        return state.get(key, kwargs.get("value", ""))

    monkeypatch.setattr(app.st, "text_area", fake_text_area)

    initial = app.auto_text_area("Benchmark", "dell_benchmark_results")
    state_key = app.widget_state_key("dell_benchmark_results", app.CURRENT_CASE_IDX)
    assert initial == "Initial results"
    assert state[state_key] == "Initial results"
    assert state[f"{state_key}__seed"] == "Initial results"

    app.D.dell_benchmark_results = "Updated diagnostics"

    refreshed = app.auto_text_area("Benchmark", "dell_benchmark_results")
    assert refreshed == "Updated diagnostics"
    assert state[state_key] == "Updated diagnostics"
    assert state[f"{state_key}__seed"] == "Updated diagnostics"


def test_auto_text_input_honors_state_labels_for_booleans(fake_state, monkeypatch):
    state, _ = fake_state
    state.debug_mode = False
    app.CURRENT_CASE_IDX = 3
    app.D = app.CaseData()
    app.D.scanner_accidental_damage = True  # legacy boolean payload

    def fake_text_input(label, **kwargs):
        key = kwargs["key"]
        return state.get(key, kwargs.get("value", ""))

    monkeypatch.setattr(app.st, "text_input", fake_text_input)

    value = app.auto_text_input(
        "Damage classification",
        "scanner_accidental_damage",
        state_labels={True: "Accidental damage", False: "Internal damage"},
    )

    state_key = app.widget_state_key("scanner_accidental_damage", app.CURRENT_CASE_IDX)
    assert value == "Accidental damage"
    assert state[state_key] == "Accidental damage"
    assert state[f"{state_key}__seed"] == "Accidental damage"
    assert app.D.scanner_accidental_damage == "Accidental damage"


def test_sync_case_text_state_updates_hidden_widgets(fake_state, monkeypatch):
    state, _ = fake_state
    state.debug_mode = False
    app.CURRENT_CASE_IDX = 0
    case = app.CaseData(company_name="Initial")
    session = app.CaseSession(case=case)
    state.case_sessions = [session]
    state.case = case
    app.D = case

    state_key = app.widget_key("company_name", app.CURRENT_CASE_IDX)
    app._register_text_widget_binding("company_name", state_key, app.CURRENT_CASE_IDX)
    state[state_key] = "Updated name"

    touched = False

    def fake_touch():
        nonlocal touched
        touched = True
        return "timestamp"

    autosaved = False

    def fake_autosave():
        nonlocal autosaved
        autosaved = True

    monkeypatch.setattr(app, "touch_case_last_modified", fake_touch)
    monkeypatch.setattr(app, "autosave", fake_autosave)

    app._sync_case_text_state(app.CURRENT_CASE_IDX)

    assert touched is True
    assert autosaved is True
    assert app.D.company_name == "Updated name"
    assert state.case_sessions[0].case.company_name == "Updated name"
    assert state[f"{state_key}__seed"] == "Updated name"
