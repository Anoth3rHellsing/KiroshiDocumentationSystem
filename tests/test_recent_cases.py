import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import KiroshiApp.services.data_manager as dm_module
import KiroshiApp.constants as constants_module

@pytest.fixture(autouse=True)
def recent_cases_directory(monkeypatch, tmp_path):
    utilities_dir = tmp_path / "utilities"
    utilities_dir.mkdir()
    recent_cases_path = utilities_dir / "recent_cases.json"
    recent_cases_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(constants_module, "UTILITIES_DIR", utilities_dir)
    monkeypatch.setattr(constants_module, "RECENT_CASES_PATH", recent_cases_path)
    monkeypatch.setattr(dm_module, "RECENT_CASES_PATH", recent_cases_path)

    return recent_cases_path


def read_recent_cases(path: Path) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_load_recent_cases_filters_non_mappings(recent_cases_directory):
    payload = [
        {"case_id": "alpha", "path": "a.json", "last_modified": "2024-01-01"},
        ["invalid"],
        "skip",  # type: ignore[list-item]
        {"case_id": "beta", "path": "b.json"},
        42,  # type: ignore[list-item]
        {"path": "c.json", "last_modified": "stamp"},
    ]
    recent_cases_directory.write_text(json.dumps(payload), encoding="utf-8")

    result = dm_module.load_recent_cases()

    assert result == [
        {"case_id": "alpha", "path": "a.json", "last_modified": "2024-01-01"},
        {"case_id": "beta", "path": "b.json", "last_modified": ""},
        {"case_id": "", "path": "c.json", "last_modified": "stamp"},
    ]


def test_update_recent_cases_computes_timestamp(recent_cases_directory, tmp_path):
    existing = [{"case_id": "legacy", "path": "legacy.json", "last_modified": "yesterday"}]
    recent_cases_directory.write_text(json.dumps(existing), encoding="utf-8")

    case_path = tmp_path / "cases" / "alpha.json"
    case_path.parent.mkdir()
    case_path.write_text(json.dumps({"case_id": "alpha"}), encoding="utf-8")

    target_time = datetime(2024, 5, 17, 13, 45, 0, tzinfo=timezone.utc)
    timestamp = target_time.timestamp()
    os.utime(case_path, (timestamp, timestamp))

    dm_module.update_recent_cases("alpha", str(case_path))

    recents = read_recent_cases(recent_cases_directory)
    assert recents[0]["case_id"] == "alpha"
    assert recents[0]["path"] == str(case_path)
    expected_last_modified = datetime.fromtimestamp(case_path.stat().st_mtime).replace(microsecond=0).isoformat()
    assert recents[0]["last_modified"] == expected_last_modified
    assert recents[1:] == existing


def test_update_recent_cases_handles_moved_file(recent_cases_directory, tmp_path):
    old_path = tmp_path / "cases" / "old" / "alpha.json"
    new_path = tmp_path / "cases" / "new" / "alpha.json"
    old_path.parent.mkdir(parents=True)
    new_path.parent.mkdir(parents=True)

    existing = [
        {"case_id": "alpha", "path": str(old_path), "last_modified": "old"},
        {"case_id": "beta", "path": "beta.json", "last_modified": "beta-ts"},
    ]
    recent_cases_directory.write_text(json.dumps(existing), encoding="utf-8")

    new_payload = {"case_id": "alpha", "last_modified": "2024-05-16T01:02:03"}
    new_path.write_text(json.dumps(new_payload), encoding="utf-8")

    dm_module.update_recent_cases("alpha", str(new_path))

    recents = read_recent_cases(recent_cases_directory)
    assert recents[0] == {
        "case_id": "alpha",
        "path": str(new_path),
        "last_modified": "2024-05-16T01:02:03",
    }
    assert recents[1:] == existing


def test_update_recent_cases_with_unreadable_json(recent_cases_directory, tmp_path):
    case_path = tmp_path / "cases" / "broken.json"
    case_path.parent.mkdir()
    case_path.write_text("{", encoding="utf-8")

    existing = [{"case_id": "gamma", "path": "gamma.json", "last_modified": "gamma-ts"}]
    recent_cases_directory.write_text(json.dumps(existing), encoding="utf-8")

    dm_module.update_recent_cases("delta", str(case_path))

    recents = read_recent_cases(recent_cases_directory)
    assert recents[0] == {
        "case_id": "delta",
        "path": str(case_path),
        "last_modified": "",
    }
    assert recents[1:] == existing
