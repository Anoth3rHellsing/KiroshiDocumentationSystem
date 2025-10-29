from __future__ import annotations

import json
import time
from pathlib import Path

from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import (
    AUTOSAVE_FILENAME,
    cases_root,
    iter_case_files,
    load_autosave,
    save_autosave,
    save_case_to_db,
)


def _make_case(**overrides: object) -> CaseData:
    data = {
        "company_name": "Acme Dental",
        "case_id": "CASE-001",
        "brief_description": "Scanner troubleshooting",
        "description": "Diagnostics and calibration were performed.",
        "solution": "Reset device",
        "additional_info": "Monitor for 24h",
    }
    data.update(overrides)
    return CaseData(**data)


def test_autosave_roundtrip(tmp_path: Path) -> None:
    case = _make_case()
    autosave_file = save_autosave(case, base_path=tmp_path)
    assert autosave_file.name == AUTOSAVE_FILENAME
    assert autosave_file.exists()

    reloaded = load_autosave(base_path=tmp_path)
    assert reloaded is not None
    assert reloaded.case_id == case.case_id
    assert reloaded.company_name == case.company_name
    assert reloaded.brief_description == case.brief_description


def test_save_case_to_db_creates_cases_directory(tmp_path: Path) -> None:
    case = _make_case(case_id="CASE/002")
    destination = save_case_to_db(case, base_path=tmp_path)
    assert destination.parent == cases_root(tmp_path)
    assert destination.suffix == ".json"

    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["case"]["case_id"] == "CASE/002"
    assert payload["case"]["company_name"] == case.company_name


def test_iter_case_files_returns_sorted_latest_first(tmp_path: Path) -> None:
    case_one = _make_case(case_id="CASE-100")
    first_path = save_case_to_db(case_one, base_path=tmp_path)
    # Ensure the filesystem registers a different modified timestamp
    time.sleep(0.01)
    case_two = _make_case(case_id="CASE-101")
    second_path = save_case_to_db(case_two, base_path=tmp_path)

    discovered = list(iter_case_files(base_path=tmp_path))
    assert discovered[0] == second_path
    assert discovered[1] == first_path
