# -*- coding: utf-8 -*-
import io
import textwrap
import re
import math
from typing import Sequence, Mapping, Iterable
from datetime import datetime
import pandas as pd
from html import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
    Preformatted,
)
from reportlab.graphics.shapes import Drawing, String
from reportlab import rl_config
from reportlab.pdfbase import pdfdoc

REPORTLAB_CHARTS_AVAILABLE = False
try:
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.lineplots import LinePlot

    REPORTLAB_CHARTS_AVAILABLE = True
except ModuleNotFoundError:
    VerticalBarChart = None
    LinePlot = None

from reportlab.graphics.widgets.markers import makeMarker

from KiroshiApp.constants import PDF_FONT_REGULAR_NAME, PDF_FONT_BOLD_NAME
from KiroshiApp.models import CaseData, ScreenshotAsset
from KiroshiApp.utils import _summarize_text, _normalize_text_field, _coerce_int, _normalize_damage_classification

# If DELL_ESCALATION_FIELD_LABELS is needed for make_pdf,
# it can be imported or passed in. It seems make_pdf uses category_dataframe
# which might need it. Let's import it from constants as it was there in the original file.
from KiroshiApp.constants import DELL_ESCALATION_FIELD_LABELS

def _ensure_pdf_fonts() -> tuple[str, str]:
    """Return the Helvetica fonts used across generated PDFs."""
    cached_fonts = getattr(_ensure_pdf_fonts, "_fonts", None)
    if cached_fonts:
        return cached_fonts

    fonts: tuple[str, str] = (PDF_FONT_REGULAR_NAME, PDF_FONT_BOLD_NAME)
    setattr(_ensure_pdf_fonts, "_fonts", fonts)
    return fonts

def _load_pdf_styles():
    """Return a stylesheet configured with the application's PDF fonts."""
    styles = getSampleStyleSheet()
    regular_font, bold_font = _ensure_pdf_fonts()

    for name in ("Normal", "BodyText", "Italic", "Code"):
        if name in styles.byName:
            styles[name].fontName = regular_font

    for name in ("Title", "Heading1", "Heading2", "Heading3", "Heading4", "Heading5", "Heading6"):
        if name in styles.byName:
            styles[name].fontName = bold_font

    ghost_style = ParagraphStyle(
        name="GhostText",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=0.1,
        leading=0.12,
        textColor=colors.white,
    )

    return styles, regular_font, bold_font, ghost_style

def _build_pdf_with_ghost_text(
    doc: SimpleDocTemplate, elements: list, snippets: Sequence[str]
) -> None:
    """Render a PDF and inject ASCII-only text for simple extractors."""
    visible: list[str] = []
    for chunk in snippets:
        text = str(chunk).strip()
        if text:
            visible.append(text)

    if visible:
        ghost_text = "\n".join(visible)
        try:
            ghost_text = ghost_text.encode("latin-1", "ignore").decode("latin-1")
        except Exception:
            ghost_text = ghost_text.encode("ascii", "ignore").decode("ascii")

        def _inject(canvas, _doc):
            canvas.saveState()
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica", 1)
            y = 12
            for line in ghost_text.split("\n"):
                raw_bytes = line.encode("latin-1", "ignore")
                literal = pdfdoc.PDFString(raw_bytes, escape=0, enc="latin-1")
                command = f"BT 1 0 0 1 8 {y:.2f} Tm {literal.format(canvas._doc).decode('latin-1')} Tj ET"
                canvas._code.append(command)
                y += 1.2
            canvas.restoreState()

        original_use_a85 = getattr(rl_config, "useA85", 1)
        try:
            rl_config.useA85 = 0
            try:
                doc.build(elements, onFirstPage=_inject, onLaterPages=_inject)
            except TypeError:
                doc.build(elements)
        finally:
            rl_config.useA85 = original_use_a85
        return

    doc.build(elements)

def _require_reportlab_charts() -> None:
    """Ensure ReportLab's chart modules are available before rendering graphics."""
    if not REPORTLAB_CHARTS_AVAILABLE:
        raise RuntimeError(
            "ReportLab chart components are unavailable. Install the 'reportlab' package "
            "with its graphics extras to enable PDF chart rendering."
        )

def _build_frequency_chart(counts: pd.DataFrame, title: str) -> Drawing:
    _require_reportlab_charts()

    chart_data = counts.head(8).copy()
    if chart_data.empty:
        raise ValueError("No hay datos para el gráfico de recurrencia.")

    regular_font, bold_font = _ensure_pdf_fonts()

    labels = [
        _summarize_text(str(label), width=32)
        for label in chart_data["analysis_label"].astype(str).tolist()
    ]
    values = chart_data["count"].astype(int).tolist()
    max_value = max(values) if values else 0

    drawing_width, drawing_height = 500, 260
    chart = VerticalBarChart()
    chart.x = 60
    chart.y = 50
    chart.height = drawing_height - 110
    chart.width = drawing_width - 110
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.angle = 35
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.fontName = regular_font
    chart.categoryAxis.visibleTicks = False
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueStep = max(1, math.ceil(max_value / 4)) if max_value else 1
    chart.valueAxis.labelTextFormat = "%d"
    chart.valueAxis.labels.fontName = regular_font
    chart.barWidth = 18
    chart.bars[0].fillColor = colors.HexColor("#3478bc")
    chart.bars.strokeColor = colors.transparent

    drawing = Drawing(drawing_width, drawing_height)
    drawing.add(chart)
    drawing.add(
        String(
            drawing_width / 2,
            drawing_height - 20,
            title,
            fontName=bold_font,
            fontSize=12,
            textAnchor="middle",
            fillColor=colors.HexColor("#1f2937"),
        )
    )
    drawing.add(
        String(
            drawing_width / 2,
            15,
            "Casos",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
        )
    )
    drawing.add(
        String(
            20,
            drawing_height / 2,
            "Frecuencia",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
            angle=90,
        )
    )

    return drawing

def _build_timeline_chart(timeline: pd.DataFrame, title: str) -> Drawing:
    _require_reportlab_charts()

    if timeline.empty:
        raise ValueError("No hay datos para la tendencia temporal.")

    regular_font, bold_font = _ensure_pdf_fonts()

    timeline_sorted = timeline.sort_values("timestamp").reset_index(drop=True)
    if timeline_sorted.empty:
        raise ValueError("No hay datos ordenados para la tendencia temporal.")

    indices = list(range(len(timeline_sorted)))
    values = timeline_sorted["count"].astype(int).tolist()
    timestamps = [
        pd.to_datetime(ts).strftime("%b %d")
        for ts in timeline_sorted["timestamp"].tolist()
    ]
    label_map = {idx: label for idx, label in zip(indices, timestamps)}

    data_points = list(zip(indices, values))
    if not data_points:
        raise ValueError("No hay puntos para el gráfico de tendencia.")

    drawing_width, drawing_height = 500, 260
    chart = LinePlot()
    chart.x = 60
    chart.y = 50
    chart.height = drawing_height - 110
    chart.width = drawing_width - 110
    chart.data = [data_points]
    chart.lines[0].strokeColor = colors.HexColor("#2ca25f")
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = makeMarker("Circle")
    chart.lines[0].symbol.size = 6
    chart.lineLabelFormat = None

    if len(indices) == 1:
        min_x = indices[0] - 1
        max_x = indices[0] + 1
    else:
        min_x = indices[0]
        max_x = indices[-1]
    chart.xValueAxis.valueMin = min_x
    chart.xValueAxis.valueMax = max_x
    chart.xValueAxis.valueSteps = indices if len(indices) > 1 else indices + [indices[0] + 1]

    def _format_label(value: float, mapping: Mapping[int, str] = label_map) -> str:
        rounded = int(round(value))
        return mapping.get(rounded, "")

    chart.xValueAxis.labelTextFormat = _format_label
    chart.xValueAxis.labels.fontSize = 8
    chart.xValueAxis.labels.fontName = regular_font
    chart.yValueAxis.valueMin = 0
    max_value = max(values) if values else 0
    chart.yValueAxis.valueStep = max(1, math.ceil(max_value / 4)) if max_value else 1
    chart.yValueAxis.labelTextFormat = "%d"
    chart.yValueAxis.labels.fontName = regular_font

    drawing = Drawing(drawing_width, drawing_height)
    drawing.add(chart)
    drawing.add(
        String(
            drawing_width / 2,
            drawing_height - 20,
            title,
            fontName=bold_font,
            fontSize=12,
            textAnchor="middle",
            fillColor=colors.HexColor("#1f2937"),
        )
    )
    drawing.add(
        String(
            drawing_width / 2,
            15,
            "Fecha",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
        )
    )
    drawing.add(
        String(
            20,
            drawing_height / 2,
            "Casos",
            fontName=regular_font,
            fontSize=9,
            textAnchor="middle",
            fillColor=colors.HexColor("#4b5563"),
            angle=90,
        )
    )

    return drawing

# Helpers for data formatting (originally in case_documentation_app.py but needed for PDF generation)
def _normalize_value_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the Value column is Arrow-friendly while preserving text entries."""
    if "Value" not in df.columns:
        return df

    df = df.copy()
    original = df["Value"].copy()
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce").fillna("").astype(str)
    numeric = pd.to_numeric(original, errors="coerce")
    numeric_mask = numeric.notna()
    if numeric_mask.any():
        df.loc[numeric_mask, "Value"] = numeric.loc[numeric_mask].map(lambda v: f"{v:g}")
    empty_mask = df["Value"] == ""
    if empty_mask.any():
        df.loc[empty_mask, "Value"] = original.loc[empty_mask].fillna("").astype(str)
    return df

def category_dataframe(
    cat: str, d: CaseData, cat_map: Mapping[str, Iterable[str]] | None
) -> pd.DataFrame:
    """Return a DataFrame with human readable field names for a category."""
    rows = []
    label_overrides = dict(DELL_ESCALATION_FIELD_LABELS)
    for fld in (cat_map or {}).get(cat, []):
        value = getattr(d, fld, "N/A")
        label = fld.replace("_", " ").title()
        if cat == "DELL ESCALATION":
            label = label_overrides.get(fld, label)
        if fld == "scanner_accidental_damage":
            label = "Damage Classification"
            raw = getattr(d, fld, "")
            value = _normalize_damage_classification(raw)
            if not value:
                value = "Not specified"
        elif isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Field": label, "Value": value})
    return _normalize_value_column(pd.DataFrame(rows))

def dell_escalation_dataframe(d: CaseData) -> pd.DataFrame:
    """Return a styled DataFrame for the Dell Escalation tab."""
    from KiroshiApp.constants import DELL_ESCALATION_FIELD_LABELS
    # Assuming 'DELL ESCALATION' is the key in cat_map logic, but we can iterate fields directly
    # if we know them. Or use category_dataframe if we had cat_map.
    # But usually we want specific fields.
    # Let's derive it from the field labels constants.

    rows = []
    for field, label in DELL_ESCALATION_FIELD_LABELS:
        value = getattr(d, field, "")
        if field == "scanner_accidental_damage":
            value = _normalize_damage_classification(value)
        elif isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Field": label, "Value": value})

    return _normalize_value_column(pd.DataFrame(rows))

def dell_escalation_plain_text(d: CaseData) -> str:
    """Return a plain text summary for Dell Escalation."""
    df = dell_escalation_dataframe(d)
    lines = []
    for _, row in df.iterrows():
        lines.append(f"{row['Field']}: {row['Value']}")
    return "\n".join(lines)

def dell_escalation_rows(d: CaseData) -> list[tuple[str, str]]:
    """Return list of (label, value) tuples for Dell Escalation."""
    df = dell_escalation_dataframe(d)
    return [(row["Field"], str(row["Value"])) for _, row in df.iterrows()]

def build_incident_report_pdf(
    context: Mapping[str, object],
    logs: str,
    user_notes: str,
    case_snapshot: list[Mapping[str, str]],
    *,
    screenshot: ScreenshotAsset | None = None,
) -> bytes:
    """Generate a PDF summarising a captured incident."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=48,
        bottomMargin=36,
    )
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    heading_style = styles["Heading3"]
    code_style = styles.get("Code", body_style)

    elements = [
        Paragraph("Kiroshi Incident Report", title_style),
        Spacer(1, 12),
        Paragraph(
            f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            body_style,
        ),
        Spacer(1, 18),
    ]

    meta_fields = [
        ("Section", context.get("section", "")),
        ("Tab", context.get("tab", "")),
        ("Trigger", context.get("trigger", "")),
        ("Timestamp", context.get("timestamp", "")),
    ]
    case_index = context.get("case_index")
    if case_index is not None:
        try:
            case_number = int(case_index) + 1
        except (TypeError, ValueError):
            case_number = case_index
        meta_fields.append(("Case index", str(case_number)))
    exception = context.get("exception")
    if exception:
        meta_fields.append(("Exception", str(exception)))

    meta_table_data = [
        [Paragraph("Field", body_style), Paragraph("Value", body_style)]
    ]
    for label, value in meta_fields:
        meta_table_data.append(
            [Paragraph(str(label), body_style), Paragraph(str(value or ""), body_style)]
        )
    meta_table = Table(meta_table_data, colWidths=[150, 360])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )
    elements.extend([meta_table, Spacer(1, 18)])

    if case_snapshot:
        elements.append(Paragraph("Case overview", heading_style))
        case_table_data: list[list[Paragraph]] = [
            [
                Paragraph("Case", body_style),
                Paragraph("Company", body_style),
                Paragraph("Summary", body_style),
                Paragraph("Priority", body_style),
                Paragraph("Active", body_style),
            ]
        ]
        case_table_data.extend(
            [
                [
                    Paragraph(str(entry.get("Case", "")), body_style),
                    Paragraph(str(entry.get("Company", "")), body_style),
                    Paragraph(str(entry.get("Summary", "")), body_style),
                    Paragraph(str(entry.get("Priority", "")), body_style),
                    Paragraph(str(entry.get("Active", "")), body_style),
                ]
                for entry in case_snapshot
            ]
        )
        case_table = Table(case_table_data, colWidths=[80, 120, 200, 70, 40])
        case_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        elements.extend([case_table, Spacer(1, 18)])

    elements.append(Paragraph("User notes", heading_style))
    elements.append(
        Paragraph(user_notes.strip() or "No user notes provided.", body_style)
    )
    elements.append(Spacer(1, 18))

    stacktrace = context.get("stacktrace")
    if stacktrace:
        elements.append(Paragraph("Stack trace", heading_style))
        elements.append(Preformatted(str(stacktrace), code_style))
        elements.append(Spacer(1, 18))

    elements.append(Paragraph("Recent logs", heading_style))
    elements.append(Preformatted(logs or "No log entries were captured.", code_style))
    elements.append(Spacer(1, 18))

    if screenshot:
        elements.append(Paragraph("Screenshot", heading_style))
        try:
            img_stream = io.BytesIO(screenshot.data)
            shot = Image(img_stream)
            max_width = 420
            if shot.drawWidth > max_width:
                scale = max_width / shot.drawWidth
                shot.drawWidth *= scale
                shot.drawHeight *= scale
            shot.hAlign = "LEFT"
            elements.extend([shot, Spacer(1, 12)])
        except Exception as exc:
            elements.append(
                Paragraph(
                    f"Unable to embed screenshot: {escape(str(exc))}",
                    body_style,
                )
            )

    ghost_snippets: list[str] = ["Kiroshi Incident Report"]
    ghost_snippets.extend(str(value or "") for _, value in meta_fields)
    ghost_snippets.append(user_notes)
    if stacktrace:
        ghost_snippets.append(stacktrace)
    ghost_snippets.append(logs)
    for entry in case_snapshot or []:
        ghost_snippets.extend(str(entry.get(key, "")) for key in ("Case", "Company", "Summary", "Priority", "Active"))

    _build_pdf_with_ghost_text(doc, elements, ghost_snippets)
    buf.seek(0)
    return buf.read()

def make_pdf(d: CaseData, cat_map) -> bytes:
    """Generate a PDF summary of the case details."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30
    )
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    body_style = styles["BodyText"]
    header_style = styles["Heading5"]
    elems = []
    ghost_snippets: list[str] = []
    for cat in cat_map:
        elems.append(Paragraph(cat, styles["Heading4"]))
        ghost_snippets.append(cat)
        df = category_dataframe(cat, d, cat_map)
        data = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
        for field, value in df.values.tolist():
            data.append([Paragraph(field, body_style), Paragraph(str(value), body_style)])
            ghost_snippets.extend([str(field), str(value)])
        t = Table(data, colWidths=[150, 350])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        elems.extend([t, Spacer(1, 12)])
    _build_pdf_with_ghost_text(doc, elems, ghost_snippets)
    buf.seek(0)
    return buf.read()

def make_tables_pdf(d: CaseData, summary: dict | None = None) -> bytes:
    """Generate a PDF with key case information for the Tables tab."""
    if summary is None:
        try:
            import streamlit as st
            summary = st.session_state.get("categorizer_summary", {})
        except ImportError:
            summary = {}
    if not isinstance(summary, Mapping):
        summary = {}

    product = summary.get("product", "")
    topic = summary.get("topic", "")
    subtopic = summary.get("subtopic", "") or ""
    hardware_test_value = ""
    if isinstance(d.hardware_test, str):
        hardware_test_value = d.hardware_test.strip()
    elif isinstance(d.hardware_test, bool):
        hardware_test_value = "Yes" if d.hardware_test else "No"
    elif d.hardware_test is not None:
        hardware_test_value = str(d.hardware_test)

    fields = [
        ("Reportable", "No"),
        ("Product Family", product),
        ("Product", topic),
        ("Sub-product", subtopic),
        ("Hardware test", hardware_test_value or "Not recorded"),
        ("Customer is TRIOS Only", "Yes" if d.customer_trios_only else "No"),
        (
            "Support fee price accepted",
            "Yes" if d.support_fee_accepted else "No",
        ),
        ("Direct payment", "No"),
        ("Dongle Subscription Info", d.dongle_number),
        ("Software Version", d.application_version),
        ("Category", product),
        ("Category Area", topic),
        ("Case type", subtopic),
        ("Responsible contact", d.email),
    ]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=30
    )
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    body_style = styles["BodyText"]
    header_style = styles["Heading5"]
    data = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
    ghost_snippets: list[str] = []
    for field, value in fields:
        data.append([Paragraph(field, body_style), Paragraph(str(value), body_style)])
        ghost_snippets.extend([str(field), str(value)])
    t = Table(data, colWidths=[180, 320])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    elements = [t]
    _build_pdf_with_ghost_text(doc, elements, ghost_snippets)
    buf.seek(0)
    return buf.read()

def generate_ai_educate_report_pdf(
    insights: Mapping[str, object],
    bug_report: Mapping[str, object] | None = None,
) -> bytes:
    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    story: list = []
    title_style = styles["Title"]
    body_style = styles["BodyText"]
    heading_style = styles["Heading4"]
    ghost_snippets: list[str] = ["AI Educate – Informe de análisis"]

    story.append(Paragraph("AI Educate – Informe de análisis", title_style))
    story.append(Spacer(1, 16))

    view_totals = insights.get("view_totals") or {}
    totals_recent = view_totals.get("30d", {}) if isinstance(view_totals, Mapping) else {}
    totals_all = view_totals.get("all_time", {}) if isinstance(view_totals, Mapping) else {}

    summary_data = [
        ["Métrica", "30 días", "Historial"],
        [
            "Casos analizados",
            str(totals_recent.get("case_total", insights.get("recent_total", 0))),
            str(totals_all.get("case_total", insights.get("case_total", 0))),
        ],
        [
            "Tipos de caso únicos",
            str(totals_recent.get("unique_labels", 0)),
            str(totals_all.get("unique_labels", 0)),
        ],
        [
            "Soluciones marcadas como bug",
            str(totals_recent.get("bug_solution_count", insights.get("bug_solution_recent", 0))),
            str(totals_all.get("bug_solution_count", insights.get("bug_solution_count", 0))),
        ],
        [
            "Casos con mención de bug",
            str(totals_recent.get("bug_mentions_count", insights.get("bug_mentions_recent", 0))),
            str(totals_all.get("bug_mentions_count", insights.get("bug_mentions_count", 0))),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[220, 120, 120])
    for row in summary_data:
        ghost_snippets.extend(str(cell) for cell in row)
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 12))

    highlight_label = insights.get("highlight_label")
    if highlight_label:
        highlight_details = insights.get("highlight_case") or {}
        highlight_text = (
            f"Caso que requiere atención: {highlight_label}"
            f" (repetido {insights.get('highlight_count', 0)} veces)."
        )
        story.append(Paragraph(highlight_text, heading_style))
        ghost_snippets.append(highlight_text)
        if highlight_details:
            detail_lines = []
            for key in ["case_id", "title", "solution_excerpt"]:
                value = highlight_details.get(key)
                if value:
                    detail_lines.append(f"{key.replace('_', ' ').title()}: {value}")
            if detail_lines:
                story.append(Paragraph("<br/>".join(detail_lines), body_style))
                ghost_snippets.extend(detail_lines)
        story.append(Spacer(1, 12))

    counts_map_raw = insights.get("counts")
    counts_map = counts_map_raw if isinstance(counts_map_raw, Mapping) else {}
    chart_specs = [
        ("30d", "Casos más frecuentes (30 días)"),
        ("all_time", "Casos más frecuentes (historial)")
    ]
    for key, title in chart_specs:
        counts_df = counts_map.get(key) if isinstance(counts_map, Mapping) else None
        if isinstance(counts_df, pd.DataFrame) and not counts_df.empty:
            try:
                drawing = _build_frequency_chart(counts_df, title)
                story.append(drawing)
                story.append(Spacer(1, 12))
                ghost_snippets.append(title)
            except Exception:
                story.append(
                    Paragraph(
                        f"No se pudo renderizar el gráfico de frecuencia ({title}).",
                        body_style,
                    )
                )
                ghost_snippets.append(title)

    timeline_map = [
        (insights.get("timeline"), "Volumen diario (30 días)"),
        (insights.get("timeline_all"), "Volumen diario (historial)"),
    ]
    for timeline_df, title in timeline_map:
        if isinstance(timeline_df, pd.DataFrame) and not timeline_df.empty:
            try:
                drawing = _build_timeline_chart(timeline_df, title)
                story.append(drawing)
                story.append(Spacer(1, 12))
                ghost_snippets.append(title)
            except Exception:
                story.append(
                    Paragraph(
                        f"No se pudieron renderizar los gráficos de tendencia ({title}).",
                        body_style,
                    )
                )
                ghost_snippets.append(title)

    recurring_df = insights.get("recurring_issue_types")
    if isinstance(recurring_df, pd.DataFrame) and not recurring_df.empty:
        story.append(Paragraph("Patrones recurrentes", heading_style))
        ghost_snippets.append("Patrones recurrentes")
        rows = [["Caso", "Recurrencias"]]
        for _, row in recurring_df.head(10).iterrows():
            rows.append(
                [str(row.get("analysis_label", "")), str(row.get("count", 0))]
            )
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        recurring_table = Table(rows, colWidths=[320, 120])
        recurring_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(recurring_table)
        story.append(Spacer(1, 12))

    root_cause_df = insights.get("common_root_causes")
    if isinstance(root_cause_df, pd.DataFrame) and not root_cause_df.empty:
        story.append(Paragraph("Causas raíz más comunes", heading_style))
        ghost_snippets.append("Causas raíz más comunes")
        rows = [["Causa", "Casos"]]
        for _, row in root_cause_df.head(10).iterrows():
            rows.append(
                [str(row.get("root_cause", "")), str(row.get("count", 0))]
            )
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        root_table = Table(rows, colWidths=[320, 120])
        root_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(root_table)
        story.append(Spacer(1, 12))

    scanner_df = insights.get("common_scanner_models")
    if isinstance(scanner_df, pd.DataFrame) and not scanner_df.empty:
        story.append(Paragraph("Modelos de escáner reportados", heading_style))
        ghost_snippets.append("Modelos de escáner reportados")
        rows = [["Modelo", "Casos"]]
        for _, row in scanner_df.head(10).iterrows():
            rows.append([str(row.get("scanner", "")), str(row.get("count", 0))])
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        scanner_table = Table(rows, colWidths=[320, 120])
        scanner_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(scanner_table)
        story.append(Spacer(1, 12))

    bug_cases = insights.get("bug_cases")
    if isinstance(bug_cases, pd.DataFrame) and not bug_cases.empty:
        story.append(Paragraph("Casos relacionados con bugs", heading_style))
        ghost_snippets.append("Casos relacionados con bugs")
        rows = [["Case ID", "Título", "Guardado"]]
        for _, row in bug_cases.head(10).iterrows():
            saved_at = row.get("saved_at") or row.get("saved_at_dt")
            if isinstance(saved_at, pd.Timestamp):
                saved_at = saved_at.strftime("%Y-%m-%d")
            rows.append([
                str(row.get("case_id", "")),
                str(row.get("title", "")),
                str(saved_at or ""),
            ])
        for row in rows:
            ghost_snippets.extend(str(cell) for cell in row)
        bug_table = Table(rows, colWidths=[120, 260, 120])
        bug_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ]
            )
        )
        story.append(bug_table)
        story.append(Spacer(1, 12))

    if bug_report:
        story.append(Paragraph("Resultados de Bug Detector", heading_style))
        ghost_snippets.append("Resultados de Bug Detector")
        summary = bug_report.get("summary")
        if summary:
            story.append(Paragraph(summary, body_style))
            ghost_snippets.append(str(summary))
        recurring = bug_report.get("recurring_patterns") or []
        if recurring:
            rows = [["Patrón", "Recurrencias"]]
            for item in recurring[:10]:
                rows.append([str(item.get("pattern", "")), str(item.get("count", 0))])
            for row in rows:
                ghost_snippets.extend(str(cell) for cell in row)
            pattern_table = Table(rows, colWidths=[300, 120])
            pattern_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), bold_font),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                    ]
                )
            )
            story.append(pattern_table)
        story.append(Spacer(1, 12))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )
    _build_pdf_with_ghost_text(doc, story, ghost_snippets)
    buffer.seek(0)
    return buffer.read()

def _collect_pattern_cases(
    pattern: str,
    dataset: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    if not dataset:
        return []
    cases = dataset.get("cases", [])
    if not isinstance(cases, list):
        return []

    # Import locally to avoid circular dependency if this utility was in main app
    from KiroshiApp.utils import extract_remote_steps_from_mapping

    normalized: list[dict[str, object]] = []
    for entry in cases:
        if not isinstance(entry, Mapping):
            continue
        label = str(
            entry.get("root_cause")
            or entry.get("title")
            or entry.get("case_id")
            or ""
        ).strip()
        if not label:
            continue
        if label.lower() != pattern.lower():
            continue
        normalized.append(
            {
                "case_id": str(entry.get("case_id") or ""),
                "title": str(entry.get("title") or ""),
                "root_cause": str(entry.get("root_cause") or ""),
                "solution": str(entry.get("solution") or ""),
                "troubleshooting": (
                    extract_remote_steps_from_mapping(entry)
                    or str(entry.get("troubleshooting") or "").strip()
                ),
                "repro_steps": str(entry.get("repro_steps") or ""),
                "additional_info": str(
                    entry.get("additional_info")
                    or entry.get("description_excerpt")
                    or ""
                ),
                "saved_at": entry.get("saved_at"),
                "source_path": entry.get("source_path"),
            }
        )
    return normalized

def generate_recurring_issue_pdf(
    pattern_entry: Mapping[str, object],
    *,
    dataset: Mapping[str, object] | None = None,
) -> bytes:
    pattern = str(pattern_entry.get("pattern") or "Patrón recurrente")
    count = int(pattern_entry.get("count") or 0)
    raw_cases = pattern_entry.get("cases")

    from KiroshiApp.utils import extract_remote_steps_from_mapping

    normalized_cases: list[dict[str, object]] = []
    if isinstance(raw_cases, list):
        normalized_cases.extend(
            [
                {
                    "case_id": str(item.get("case_id") or ""),
                    "title": str(item.get("title") or ""),
                    "root_cause": str(item.get("root_cause") or ""),
                    "solution": str(item.get("solution") or ""),
                    "troubleshooting": (
                        extract_remote_steps_from_mapping(item)
                        or str(item.get("troubleshooting") or "").strip()
                    ),
                    "repro_steps": str(item.get("repro_steps") or ""),
                    "additional_info": str(
                        item.get("additional_info")
                        or item.get("description_excerpt")
                        or ""
                    ),
                    "saved_at": item.get("saved_at"),
                    "source_path": item.get("source_path"),
                }
                for item in raw_cases
                if isinstance(item, Mapping)
            ]
        )

    if not normalized_cases:
        normalized_cases = _collect_pattern_cases(pattern, dataset)

    if not normalized_cases:
        raise ValueError("No hay casos suficientes para generar la guía del patrón.")

    def _unique_text(values: Iterable[str]) -> str:
        seen: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in seen:
                seen.append(cleaned)
        return "\n\n".join(seen)

    root_causes = _unique_text(case.get("root_cause", "") for case in normalized_cases)
    repro_text = _unique_text(case.get("repro_steps", "") for case in normalized_cases)
    troubleshooting_text = _unique_text(
        case.get("troubleshooting", "") for case in normalized_cases
    )
    solution_text = _unique_text(case.get("solution", "") for case in normalized_cases)
    notes_text = _unique_text(
        case.get("additional_info", "") for case in normalized_cases
    )

    styles, regular_font, bold_font, ghost_style = _load_pdf_styles()
    body_style = styles["BodyText"]
    heading_style = styles["Heading3"]
    header_style = styles["Heading5"]
    ghost_snippets: list[str] = [
        pattern,
        str(count),
        root_causes,
        repro_text,
        troubleshooting_text,
        solution_text,
        notes_text,
    ]

    def _to_paragraph(text: str) -> Paragraph:
        content = text.strip()
        if not content:
            content = "—"
        else:
            content = escape(content).replace("\n", "<br/>")
        return Paragraph(content, body_style)

    guide_rows = [
        [Paragraph("Patrón", header_style), _to_paragraph(pattern)],
        [
            Paragraph("Casos detectados", header_style),
            _to_paragraph(str(count or len(normalized_cases))),
        ],
        [Paragraph("Causa raíz destacada", header_style), _to_paragraph(root_causes)],
        [Paragraph("Cómo reproducir", header_style), _to_paragraph(repro_text)],
        [
            Paragraph("Troubleshooting aplicado", header_style),
            _to_paragraph(troubleshooting_text),
        ],
        [
            Paragraph("Solución documentada", header_style),
            _to_paragraph(solution_text),
        ],
        [Paragraph("Notas adicionales", header_style), _to_paragraph(notes_text)],
    ]

    guide_table = Table(guide_rows, colWidths=[170, 330])
    guide_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )

    detail_rows: list[list[Paragraph]] = [
        [
            Paragraph("Case ID", header_style),
            Paragraph("Título", header_style),
            Paragraph("Cómo reproducir", header_style),
            Paragraph("Troubleshooting", header_style),
            Paragraph("Solución", header_style),
        ]
    ]

    detail_rows.extend(
        [
            [
                _to_paragraph(case.get("case_id", "")),
                _to_paragraph(case.get("title", "")),
                _to_paragraph(case.get("repro_steps", "")),
                _to_paragraph(case.get("troubleshooting", "")),
                _to_paragraph(case.get("solution", "")),
            ]
            for case in normalized_cases
        ]
    )
    for case in normalized_cases:
        ghost_snippets.extend(
            str(case.get(key, ""))
            for key in ("case_id", "title", "repro_steps", "troubleshooting", "solution")
        )

    detail_table = Table(
        detail_rows,
        colWidths=[70, 120, 110, 110, 120],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
            ]
        )
    )

    story: list = []
    story.append(Paragraph("Guía de patrón recurrente", heading_style))
    story.append(Spacer(1, 12))
    story.append(guide_table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Casos analizados", heading_style))
    story.append(Spacer(1, 8))
    story.append(detail_table)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=30,
    )
    _build_pdf_with_ghost_text(doc, story, ghost_snippets)
    buffer.seek(0)
    return buffer.read()
