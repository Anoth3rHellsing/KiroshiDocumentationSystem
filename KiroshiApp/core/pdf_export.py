"""PDF export utilities for ``CaseData`` records."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .model import CaseData, RemoteSessionEntry, TrackingData

ESSENTIAL_FIELDS: Sequence[tuple[str, str]] = (
    ("case_id", "Case ID"),
    ("company_name", "Empresa"),
    ("brief_description", "Resumen breve"),
)


def _as_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    cleaned = (text or "").strip().replace("\n", "<br/>")
    return Paragraph(cleaned or "—", style)


def _key_value_table(rows: Sequence[tuple[str, str]], style: ParagraphStyle) -> Table:
    data: list[list[Paragraph]] = [
        [Paragraph("<b>Campo</b>", style), Paragraph("<b>Valor</b>", style)]
    ]
    for key, value in rows:
        data.append([Paragraph(f"<b>{key}</b>", style), _as_paragraph(value, style)])
    table = Table(data, colWidths=[170, 370])
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


def _filtered_rows(pairs: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(label, value) for label, value in pairs if (value or "").strip()]


def _case_overview_rows(case: CaseData) -> list[tuple[str, str]]:
    return _filtered_rows(
        [
            ("Case ID", case.case_id),
            ("Empresa", case.company_name),
            ("Descripción breve", case.brief_description),
            ("Descripción", case.description),
            ("Solución", case.solution),
            ("Contacto", case.caller_name),
            ("Teléfono", case.phone_number),
            ("Correo", case.email),
            ("ID de suscripción", case.subscription_id),
            ("Versión de la aplicación", case.application_version),
            ("Información adicional", case.additional_info),
        ]
    )


def _tracking_rows(tracking: TrackingData) -> list[tuple[str, str]]:
    return _filtered_rows(
        [
            ("Activo", "Sí" if tracking.active else "No"),
            ("Tipo", tracking.type),
            ("Categoría", tracking.category),
            ("Estado", tracking.status),
            ("Prioridad", tracking.priority),
            ("Ticket", tracking.ticket_number),
            ("Día de creación", tracking.creation_day),
            ("Enlace", tracking.case_link),
            ("Arribo esperado", tracking.expected_arrival_date),
            ("Service tag", tracking.service_tag),
        ]
    )


def _hardware_rows(case: CaseData) -> list[tuple[str, str]]:
    return _filtered_rows(
        [
            ("Prueba de hardware", case.hardware_test),
            ("Service tag Dell", case.service_tag),
            ("Modelo PC", case.pc_model),
            ("Versión de Windows", case.windows_version),
            ("Versión BIOS", case.bios_version),
            ("Tarjeta gráfica", case.graphics_card),
            ("Procesador", case.processor),
            ("Garantía", case.warranty),
            ("Scanner S/N", case.scanner_sn),
            ("Base S/N", case.base_sn),
            ("Versión módulo TRIOS", case.trios_module_version),
            ("Despliegue dongle", case.dongle_deployment_date),
            ("Reemplazos de scanner", str(case.scanner_previous_replacements)),
            ("Daño accidental", case.scanner_accidental_damage),
            ("Inicio de problema", case.dell_issue_start_date),
            ("Command Updates", case.dell_command_updates_status),
            ("Opciones de energía", case.dell_power_options_setup),
            ("Optimizer", case.dell_optimizer_setup),
            ("Intel PPM", case.dell_intel_ppm_installed),
            ("CPU speed/throttling", case.dell_cpu_speed_or_throttling),
            ("GPU integrada", case.dell_gpu_usage_integrated),
            ("GPU dedicada", case.dell_gpu_usage_dedicated),
            ("Uso de CPU", case.dell_cpu_utilization),
            ("Benchmark", case.dell_benchmark_results),
            ("Ultra resolución", case.dell_ultra_resolution_support),
            ("Drivers GPU", case.dell_gpu_driver_versions),
            ("Reliability monitor", case.dell_reliability_monitor_results),
            ("Diagnostics", case.dell_diagnostics_results),
            ("Windows reinstalado", case.dell_windows_reimaged),
        ]
    )


def _build_remote_session_table(
    sessions: Iterable[RemoteSessionEntry], style: ParagraphStyle
) -> Table | None:
    rows: list[list[Paragraph]] = []
    for idx, entry in enumerate(sessions, start=1):
        title = entry.display_title(idx)
        notes = _as_paragraph(entry.notes or "—", style)
        rows.append([Paragraph(title, style), notes])
    if not rows:
        return None
    table = Table([[Paragraph("<b>Sesión</b>", style), Paragraph("<b>Notas</b>", style)], *rows], colWidths=[170, 370])
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


def validate_case_for_export(case: CaseData) -> list[str]:
    missing: list[str] = []
    for field_name, label in ESSENTIAL_FIELDS:
        value = getattr(case, field_name, "")
        if not str(value or "").strip():
            missing.append(label)
    return missing


def _story_for_case(case: CaseData) -> list:
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.wordWrap = "CJK"
    heading = styles["Heading2"]
    story: list = []

    story.append(Paragraph("Resumen de caso", styles["Title"]))
    story.append(Spacer(1, 12))

    overview_rows = _case_overview_rows(case)
    if overview_rows:
        story.append(_key_value_table(overview_rows, body))
    if case.remote_steps:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Pasos remotos</b>", heading))
        story.append(_as_paragraph(case.remote_steps, body))

    tracking_rows = _tracking_rows(case.tracking or TrackingData())
    if tracking_rows:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Seguimiento</b>", heading))
        story.append(_key_value_table(tracking_rows, body))

    remote_table = _build_remote_session_table(case.remote_sessions, body)
    if remote_table is not None:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Sesiones remotas</b>", heading))
        story.append(remote_table)

    if case.include_hardware_fields:
        hardware_rows = _hardware_rows(case)
        if hardware_rows:
            story.append(Spacer(1, 12))
            story.append(Paragraph("<b>Diagnóstico de hardware</b>", heading))
            story.append(_key_value_table(hardware_rows, body))

    return story


def export_case_summary(case: CaseData, output_path: Path | None = None) -> bytes | Path:
    """Generate a PDF summary for ``case``.

    If ``output_path`` is provided the file is written there and the path is
    returned; otherwise, the PDF bytes are returned.
    """

    doc_buffer = BytesIO()
    doc = SimpleDocTemplate(doc_buffer, pagesize=letter, title=case.case_id or "Caso")
    story = _story_for_case(case)
    doc.build(story)
    pdf_bytes = doc_buffer.getvalue()

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
        return output_path

    return pdf_bytes


__all__ = [
    "ESSENTIAL_FIELDS",
    "export_case_summary",
    "validate_case_for_export",
]
