"""PDF helpers for the experimental desktop prototype."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .model import CaseData

PDF_HEADER = b"%PDF-1.4\n"


def _format_case_summary(case: CaseData, extra_sections: Sequence[tuple[str, str]] | None = None) -> str:
    sections: list[str] = []
    sections.append(f"Case ID: {case.case_id}")
    sections.append(f"Company: {case.company_name}")
    if case.brief_description:
        sections.append(f"Summary: {case.brief_description}")
    if case.description:
        sections.append(f"Description: {case.description}")
    if case.solution:
        sections.append(f"Solution: {case.solution}")
    if case.additional_info:
        sections.append(f"Additional Info: {case.additional_info}")
    if case.remote_sessions:
        notes = "; ".join(entry.notes for entry in case.remote_sessions if entry.notes)
        if notes:
            sections.append(f"Remote Sessions: {notes}")
    if extra_sections:
        for title, content in extra_sections:
            sections.append(f"{title}: {content}")
    return "\n".join(sections)


def _build_stub_pdf(case: CaseData, attachments: Iterable[Path] | None, extra_sections: Sequence[tuple[str, str]] | None) -> bytes:
    body_lines = ["BT", "/F1 12 Tf", "50 750 Td"]
    summary = _format_case_summary(case, extra_sections)
    for line in summary.splitlines() or ["Case export"]:
        escaped = line.replace("(", r"\(").replace(")", r"\)")
        body_lines.append(f"({escaped}) Tj")
        body_lines.append("0 -18 Td")
    if attachments:
        body_lines.append("% Attachments included:")
        for path in attachments:
            body_lines.append(f"% - {Path(path).name}")
    body_lines.append("ET")
    stream = "\n".join(body_lines)
    pdf_template = (
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        "4 0 obj<< /Length {length} >>stream\n{stream}\nendstream endobj\n"
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        "xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n"
        "0000000114 00000 n \n0000000278 00000 n \n0000000395 00000 n \n"
        "trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n489\n%%EOF"
    )
    stream_bytes = stream.encode("utf-8")
    pdf_bytes = PDF_HEADER + pdf_template.format(length=len(stream_bytes), stream=stream).encode("utf-8")
    return pdf_bytes


def generate_case_pdf(
    case: CaseData,
    *,
    output_path: Path | None = None,
    attachments: Iterable[Path] | None = None,
    extra_sections: Sequence[tuple[str, str]] | None = None,
) -> bytes | Path:
    """Create a minimal PDF representation of a case."""

    pdf_bytes = _build_stub_pdf(case, attachments, extra_sections)
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return output_path
    return pdf_bytes
