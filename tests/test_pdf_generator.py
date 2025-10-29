from __future__ import annotations

from pathlib import Path

from KiroshiApp.core.model import CaseData, RemoteSessionEntry, TrackingData
from KiroshiApp.core.pdf_generator import generate_case_pdf


def _make_case(**overrides: object) -> CaseData:
    data = {
        "company_name": "Acme Dental",
        "case_id": "CASE-500",
        "brief_description": "Scanner realignment",
        "description": "Performed calibration and verified test scans.",
        "solution": "Recalibrated scanner arm",
        "remote_sessions": [
            RemoteSessionEntry(title="Calibration", notes="Adjusted mirror"),
        ],
        "tracking": TrackingData(active=True, status="In progress", priority="High"),
    }
    data.update(overrides)
    return CaseData(**data)


def test_generate_case_pdf_returns_bytes() -> None:
    case = _make_case()
    pdf_bytes = generate_case_pdf(case)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_case_pdf_writes_file(tmp_path: Path) -> None:
    case = _make_case()
    attachment = tmp_path / "log.txt"
    attachment.write_text("Diagnostics log", encoding="utf-8")
    output_path = tmp_path / "exports" / "case.pdf"

    path = generate_case_pdf(
        case,
        output_path=output_path,
        attachments=[attachment],
        extra_sections=[("Notas", "Seguimiento completado")],
    )

    assert path == output_path
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"%PDF")
