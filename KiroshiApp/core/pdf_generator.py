"""PDF helpers for the experimental desktop prototype."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .model import CaseData, RemoteSessionEntry


def _format_metadata(case: CaseData) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    fields.append(("Case ID", case.case_id or "N/A"))
    if case.company_name:
        fields.append(("Company", case.company_name))
    if case.brief_description:
        fields.append(("Summary", case.brief_description))
    if case.description:
        fields.append(("Description", case.description))
    if case.solution:
        fields.append(("Solution", case.solution))
    if case.additional_info:
        fields.append(("Additional Info", case.additional_info))
    if case.tracking and getattr(case.tracking, "status", ""):
        fields.append(("Tracking Status", case.tracking.status))
    if case.tracking and getattr(case.tracking, "priority", ""):
        fields.append(("Priority", case.tracking.priority))
    return fields


def _build_remote_session_table(sessions: Iterable[RemoteSessionEntry]) -> Table | None:
    rows: list[list[str]] = []
    for idx, entry in enumerate(sessions, start=1):
        title = entry.display_title(idx)
        notes = entry.notes.strip() or "—"
        rows.append([title, notes])
    if not rows:
        return None
    table = Table([["Session", "Notes"], *rows], colWidths=[180, 350])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    return table


def _story_for_case(
    case: CaseData,
    attachments: Iterable[Path] | None,
    extra_sections: Sequence[tuple[str, str]] | None,
) -> list:
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.spaceAfter = 6
    heading = styles["Heading2"]
    story: list = []

    story.append(Paragraph("Kiroshi Case Summary", styles["Title"]))
    story.append(Spacer(1, 12))

    for label, value in _format_metadata(case):
        story.append(Paragraph(f"<b>{label}:</b> {value}", body))

    if extra_sections:
        for title, content in extra_sections:
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>{title}:</b> {content}", body))

    table = _build_remote_session_table(case.remote_sessions)
    if table is not None:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Remote Sessions", heading))
        story.append(table)

    attachment_list = list(Path(p) for p in (attachments or []))
    if attachment_list:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Attachments", heading))
        for path in attachment_list:
            story.append(Paragraph(f"• {path.name}", body))

    return story


def generate_case_pdf(
    case: CaseData,
    *,
    output_path: Path | None = None,
    attachments: Iterable[Path] | None = None,
    extra_sections: Sequence[tuple[str, str]] | None = None,
) -> bytes | Path:
    """Create a PDF representation of ``case`` using ReportLab."""

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=case.case_id or "Case Summary")
    story = _story_for_case(case, attachments, extra_sections)
    doc.build(story)
    pdf_bytes = buffer.getvalue()

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return output_path

    return pdf_bytes
