"""PDF export utilities for case summaries."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .model import CaseData, RemoteSessionEntry, format_remote_sessions_summary
from .utils import format_timestamp, utc_now_iso


class CasePdfBuilder:
    """Helper responsible for turning ``CaseData`` instances into PDFs."""

    def __init__(self) -> None:
        self.styles = _load_styles()

    def build_story(
        self,
        case: CaseData,
        *,
        attachments: Sequence[Path] | None = None,
        extra_sections: Sequence[tuple[str, str]] | None = None,
    ) -> Iterable:
        title_style = self.styles["Title"]
        body_style = self.styles["BodyText"]
        heading_style = self.styles["Heading"]
        code_style = self.styles["Code"]

        yield Paragraph("Kiroshi Case Summary", title_style)
        yield Spacer(1, 12)
        yield Paragraph(f"Generated {format_timestamp(utc_now_iso())}", body_style)
        yield Spacer(1, 18)

        yield from self._render_overview(case, body_style)
        yield Spacer(1, 18)

        if case.description.strip():
            yield Paragraph("Case description", heading_style)
            yield Paragraph(case.description.strip(), body_style)
            yield Spacer(1, 12)

        if case.remote_sessions:
            yield Paragraph("Remote sessions", heading_style)
            for block in self._render_remote_sessions(case.remote_sessions, body_style):
                yield block
            yield Spacer(1, 12)
        elif case.remote_steps:
            yield Paragraph("Remote steps", heading_style)
            yield Preformatted(case.remote_steps, code_style)
            yield Spacer(1, 12)

        if case.tracking and case.tracking.active:
            yield Paragraph("Tracking", heading_style)
            yield from self._render_tracking(case, body_style)
            yield Spacer(1, 12)

        if attachments:
            yield Paragraph("Attachments", heading_style)
            items = [Paragraph(f"• {path.name}", body_style) for path in attachments]
            for item in items:
                yield item
            yield Spacer(1, 12)

        if extra_sections:
            for heading, content in extra_sections:
                if not content:
                    continue
                yield Paragraph(heading, heading_style)
                yield Paragraph(content, body_style)
                yield Spacer(1, 12)

        summary = format_remote_sessions_summary(case.remote_sessions)
        if summary and not case.remote_sessions:
            yield Paragraph("Troubleshooting summary", heading_style)
            yield Paragraph(summary, body_style)

    def _render_overview(self, case: CaseData, body_style: ParagraphStyle):
        rows = [
            ("Company", case.company_name),
            ("Case ID", case.case_id),
            ("Subscription", case.subscription_id),
            ("Caller", case.caller_name),
            ("Phone", case.phone_number),
            ("Email", case.email),
            ("Brief", case.brief_description),
            ("Application", case.application_version),
        ]
        rows = [(label, value) for label, value in rows if value]
        if not rows:
            return
        table_data = [
            [Paragraph("Field", body_style), Paragraph("Value", body_style)]
        ]
        for label, value in rows:
            table_data.append([Paragraph(label, body_style), Paragraph(str(value), body_style)])
        table = Table(table_data, colWidths=[120, 360])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        yield table

    def _render_remote_sessions(
        self, sessions: Sequence[RemoteSessionEntry], body_style: ParagraphStyle
    ):
        for idx, session in enumerate(sessions, start=1):
            header = session.display_title(idx)
            timestamps: list[str] = []
            if session.created_at:
                timestamps.append(f"started {session.created_at}")
            if session.updated_at and session.updated_at != session.created_at:
                timestamps.append(f"updated {session.updated_at}")
            subtitle = f" ({', '.join(timestamps)})" if timestamps else ""
            yield Paragraph(f"{header}{subtitle}", self.styles["Heading"])
            notes = session.notes.strip() or "No notes provided."
            style = code_style if "\n" in notes else body_style
            yield Preformatted(notes, style) if style is code_style else Paragraph(notes, style)
            yield Spacer(1, 8)

    def _render_tracking(self, case: CaseData, body_style: ParagraphStyle):
        tracking = case.tracking
        if not tracking:
            return
        rows = [
            ("Type", tracking.type),
            ("Category", tracking.category),
            ("Status", tracking.status),
            ("Priority", tracking.priority),
            ("Ticket", tracking.ticket_number),
            ("Case link", tracking.case_link),
            ("Created", tracking.creation_day),
            ("Expected arrival", tracking.expected_arrival_date),
            ("Service tag", tracking.service_tag),
        ]
        rows = [(label, value) for label, value in rows if value]
        if not rows:
            yield Paragraph("No tracking metadata available.", body_style)
            return
        table = Table(
            [[Paragraph(label, body_style), Paragraph(str(value), body_style)] for label, value in rows],
            colWidths=[120, 360],
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        yield table


def _load_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Heading",
            parent=styles["Heading2"],
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Code",
            parent=styles["BodyText"],
            fontName="Courier",
            leading=10,
        )
    )
    return styles


def generate_case_pdf(
    case: CaseData,
    *,
    output_path: Path | None = None,
    attachments: Sequence[Path] | None = None,
    extra_sections: Sequence[tuple[str, str]] | None = None,
) -> bytes | Path:
    """Generate a PDF summarising ``case``.

    When ``output_path`` is ``None`` the PDF bytes are returned. Otherwise the
    document is written to disk and the resulting path is returned.
    """

    builder = CasePdfBuilder()
    story = list(
        builder.build_story(
            case,
            attachments=attachments,
            extra_sections=extra_sections,
        )
    )
    if output_path is None:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=48,
            bottomMargin=48,
        )
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=48,
        bottomMargin=48,
    )
    doc.build(story)
    return output_path
