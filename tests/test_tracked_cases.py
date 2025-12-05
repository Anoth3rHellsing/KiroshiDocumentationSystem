"""Tests for tracked case utilities in ``case_documentation_app``."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import case_documentation_app as app


class DummySessionState(dict):
    """Dictionary with attribute access used to stub ``st.session_state``."""

    def __getattr__(self, item):  # pragma: no cover - attribute fallback
        try:
            return self[item]
        except KeyError as exc:  # pragma: no cover - mimic Streamlit behaviour
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):  # pragma: no cover - attribute fallback
        self[key] = value


@pytest.fixture()
def streamlit_stubs(monkeypatch):
    """Provide a deterministic Streamlit facade for tests."""

    state = DummySessionState()
    toast_calls: list[str] = []
    success_calls: list[str] = []
    error_calls: list[str] = []
    rerun_calls: list[None] = []

    monkeypatch.setattr(app.st, "session_state", state, raising=False)
    monkeypatch.setattr(app.st, "toast", lambda message: toast_calls.append(message), raising=False)
    monkeypatch.setattr(app.st, "success", lambda message: success_calls.append(message), raising=False)
    monkeypatch.setattr(app.st, "error", lambda message: error_calls.append(message), raising=False)
    monkeypatch.setattr(app.st, "rerun", lambda: rerun_calls.append(None), raising=False)

    return state, toast_calls, success_calls, error_calls, rerun_calls


def iso_mtime(path: Path) -> str:
    """Return the ISO formatted modification timestamp for a path."""

    return datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0).isoformat()


def test_load_tracked_cases_filters_and_normalizes(tmp_path, monkeypatch):
    database_dir = tmp_path / "db"
    legacy_dir = tmp_path / "legacy"
    database_dir.mkdir()
    legacy_dir.mkdir()

    monkeypatch.setattr(app, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(app, "TRACKED_CASES_DIR", legacy_dir)

    modern_active_path = database_dir / "CASE-001.json"
    modern_active_path.write_text(
        json.dumps(
            {
                "case_id": "CASE-001",
                "company_name": "Acme Corp",
                "tracking": {
                    "active": True,
                    "priority": "Ultra",  # invalid option should normalize
                    "status": "Working",
                    "type": "Dell",
                    "category": "Hardware",
                },
            }
        ),
        encoding="utf-8",
    )

    # Inactive tracking file should be ignored entirely.
    (database_dir / "CASE-002.json").write_text(
        json.dumps({"case_id": "CASE-002", "tracking": {"active": False}}),
        encoding="utf-8",
    )

    legacy_path = legacy_dir / "CASE-LEGACY_Active.json"
    legacy_path.write_text(
        json.dumps(
            {
                "case_id": "CASE-LEGACY",
                "company": "Legacy Co",
                "status": "Pending",
                "priority": "Unknown",  # invalid -> normalized
            }
        ),
        encoding="utf-8",
    )

    cases = app.load_tracked_cases()
    paths = {case["path"]: case for case in cases}

    assert str(modern_active_path) in paths
    assert str(legacy_path) in paths
    assert str(database_dir / "CASE-002.json") not in paths

    modern_case = paths[str(modern_active_path)]
    assert modern_case["priority"] == app.DEFAULT_TRACKING_PRIORITY
    assert modern_case["is_legacy"] is False
    assert modern_case["last_modified"] == iso_mtime(modern_active_path)

    legacy_case = paths[str(legacy_path)]
    assert legacy_case["priority"] == app.DEFAULT_TRACKING_PRIORITY
    assert legacy_case["is_legacy"] is True
    assert legacy_case["last_modified"] == iso_mtime(legacy_path)


def test_priority_and_status_updates_patch(monkeypatch, streamlit_stubs):
    state, toast_calls, _, error_calls, _ = streamlit_stubs

    monkeypatch.setattr(app, "CURRENT_CASE_IDX", 0, raising=False)
    tracking = SimpleNamespace(priority="High", status="Old", active=True)
    monkeypatch.setattr(app, "D", SimpleNamespace(case_id="CASE-123", tracking=tracking), raising=False)

    update_calls: list[tuple[str, dict | None, dict]] = []

    def fake_update_tracked_case_file(path, *, tracking_updates=None, **updates):
        update_calls.append((path, tracking_updates, updates))
        return "2024-05-01T12:34:56Z"

    touches: list[str | None] = []

    def fake_touch_case_last_modified(*, timestamp=None):
        touches.append(timestamp)
        return timestamp

    monkeypatch.setattr(app, "update_tracked_case_file", fake_update_tracked_case_file)
    monkeypatch.setattr(app, "touch_case_last_modified", fake_touch_case_last_modified)

    normalized, timestamp = app._apply_tracked_priority_update(
        "path.json", "Ultra", case_id="CASE-123", is_legacy=False
    )

    assert normalized == app.DEFAULT_TRACKING_PRIORITY
    assert timestamp == "2024-05-01T12:34:56Z"
    assert update_calls[0] == (
        "path.json",
        {"priority": app.DEFAULT_TRACKING_PRIORITY},
        {},
    )
    assert touches == ["2024-05-01T12:34:56Z"]
    assert tracking.priority == app.DEFAULT_TRACKING_PRIORITY
    assert state[app.widget_key("track_priority", 0)] == app.DEFAULT_TRACKING_PRIORITY

    status_key = "status_key"
    state[status_key] = "Delivered"
    app.update_tracked_status("path.json", status_key, case_id="CASE-123", is_legacy=False)

    assert update_calls[1] == (
        "path.json",
        {"status": "Delivered"},
        {},
    )
    assert touches == ["2024-05-01T12:34:56Z", "2024-05-01T12:34:56Z"]
    assert tracking.status == "Delivered"
    assert state[app.widget_key("track_status", 0)] == "Delivered"
    assert toast_calls == ["Status updated"]
    assert error_calls == []


def test_untrack_case_for_modern_and_legacy(tmp_path, monkeypatch, streamlit_stubs):
    state, toast_calls, success_calls, error_calls, rerun_calls = streamlit_stubs

    database_dir = tmp_path / "db"
    legacy_dir = tmp_path / "legacy"
    database_dir.mkdir()
    legacy_dir.mkdir()

    monkeypatch.setattr(app, "DATABASE_DIR", database_dir)
    monkeypatch.setattr(app, "TRACKED_CASES_DIR", legacy_dir)
    monkeypatch.setattr(app, "CURRENT_CASE_IDX", 0, raising=False)

    recent_updates: list[tuple[str, str]] = []

    def fake_update_recent_cases(case_id, path):
        recent_updates.append((case_id, path))

    monkeypatch.setattr(app, "update_recent_cases", fake_update_recent_cases)

    # Modern tracked case - should simply flip the active flag and update session state.
    modern_tracking = SimpleNamespace(active=True, status="Old", priority="High")
    monkeypatch.setattr(app, "D", SimpleNamespace(case_id="CASE-001", tracking=modern_tracking), raising=False)
    state.track_case = True

    modern_path = database_dir / "CASE-001.json"
    modern_path.write_text(
        json.dumps({"case_id": "CASE-001", "tracking": {"active": True, "status": "Old"}}),
        encoding="utf-8",
    )

    app.untrack_case(str(modern_path))

    modern_payload = json.loads(modern_path.read_text(encoding="utf-8"))
    assert modern_payload["tracking"]["active"] is False
    assert modern_tracking.active is False
    assert state.track_case is False
    assert toast_calls[-1] == "Case removed from tracking."
    assert rerun_calls[-1] is None
    assert error_calls == []
    assert success_calls == []
    assert recent_updates[-1] == ("CASE-001", str(modern_path))

    # Legacy tracked case - should migrate into the database directory.
    legacy_payload = {
        "case_id": "CASE-LEGACY",
        "company": "Legacy Co",
        "status": "Pending",
        "path": "legacy/path.json",
    }
    legacy_path = legacy_dir / "CASE-LEGACY_Active.json"
    legacy_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    # Swap out the in-memory case to avoid mutating the previous instance.
    monkeypatch.setattr(app, "D", SimpleNamespace(case_id="CASE-LEGACY", tracking=SimpleNamespace(active=True)), raising=False)
    state.track_case = True

    app.untrack_case(str(legacy_path), is_legacy=True)

    migrated_path = database_dir / "CASE-LEGACY.json"
    assert migrated_path.exists()
    migrated_payload = json.loads(migrated_path.read_text(encoding="utf-8"))
    assert migrated_payload["status"] == "Pending"
    assert "path" not in migrated_payload
    assert not legacy_path.exists()
    assert toast_calls[-1] == "Case removed from tracking."
    assert rerun_calls[-1] is None
    assert recent_updates[-1] == ("CASE-LEGACY", str(migrated_path))
    assert error_calls == []

