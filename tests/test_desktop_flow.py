from __future__ import annotations

from pathlib import Path

from KiroshiApp.core.model import CaseData, RemoteSessionEntry, TrackingData
from KiroshiApp.core.pdf_generator import generate_case_pdf
from KiroshiApp.core.storage import load_autosave, save_autosave, save_case_to_db
from KiroshiApp.core.tracking import list_tracked_cases, start_tracking, stop_tracking


def _build_case() -> CaseData:
    case = CaseData(
        company_name="Acme Dental",
        case_id="CASE-777",
        brief_description="Scanner noise",
        description="Customer reported abnormal scanner noise during use.",
        solution="Cleaned scanner head",
        additional_info="Follow-up call scheduled",
        remote_sessions=[RemoteSessionEntry(title="Session 1", notes="Checked firmware")],
        tracking=TrackingData(active=True, status="Monitoring", priority="High"),
    )
    case.validate()
    return case


def test_full_case_flow(tmp_path: Path) -> None:
    case = _build_case()

    autosave_path = save_autosave(case, base_path=tmp_path)
    assert autosave_path.exists()

    reloaded = load_autosave(base_path=tmp_path)
    assert reloaded is not None
    assert reloaded.case_id == case.case_id

    export_path = tmp_path / "exports" / "case.pdf"
    generate_case_pdf(case, output_path=export_path)
    assert export_path.exists()

    db_path = save_case_to_db(case, base_path=tmp_path)
    assert db_path.exists()

    tracked_path = start_tracking(case, base_path=tmp_path)
    assert tracked_path.exists()

    tracked_cases = list_tracked_cases(base_path=tmp_path)
    assert any(record.case.case_id == case.case_id for record in tracked_cases)

    closed = stop_tracking(case.case_id, base_path=tmp_path)
    assert closed is True

    remaining = list_tracked_cases(base_path=tmp_path)
    assert not any(
        record.path.parent.name == "TrackedCases" and record.case.case_id == case.case_id
        for record in remaining
    )
