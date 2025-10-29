"""Tracking tab implementation for the experimental desktop prototype."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.model import CaseData, TrackingData
from KiroshiApp.core.tracking import TrackedCaseRecord, list_tracked_cases


def _parse_date(value: object) -> date | None:
    """Return a :class:`datetime.date` parsed from loose user input."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        normalized = value.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(normalized, fmt).date()
            except ValueError:
                continue
        try:
            normalized = normalized.replace("Z", "")
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            return None
    return None


def _sla_status(tracking: TrackingData) -> str:
    """Return a human friendly SLA indicator for the case."""

    today = date.today()
    expected = _parse_date(tracking.expected_arrival_date)
    if expected:
        delta = (expected - today).days
        if delta >= 2:
            return "En plazo"
        if delta >= 0:
            return "Aviso"
        return "Fuera de plazo"

    created = _parse_date(tracking.creation_day)
    if created:
        age = (today - created).days
        if age <= 2:
            return "En plazo"
        if age <= 5:
            return "Aviso"
        return "Fuera de plazo"
    return "Sin datos"

from KiroshiApp.core.model import CaseData


class TrackingTab(QWidget):
    """Visual dashboard that monitors tracked cases on disk."""

    loadRequested = Signal(CaseData)
    untrackRequested = Signal(str)
    closeRequested = Signal(str)

    def __init__(
        self,
        *,
        base_path: Path | str | None = None,
        reminders_config: dict[str, Any] | None = None,
        second_line_enabled: bool = False,
    ) -> None:
        super().__init__()
        self._base_path = base_path
        self._reminders_config = reminders_config or {}
        self._records: list[TrackedCaseRecord] = []
        self._closed_cases: list[str] = []

        self._header_label = QLabel(
            "El Control Tower refleja los casos activos guardados con seguimiento."
        )
        self._header_label.setWordWrap(True)

        self._gate_label = QLabel(
            "Activa el modo 2nd Line en Configuración para habilitar acciones de seguimiento."
        )
        self._gate_label.setWordWrap(True)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            [
                "Caso",
                "Cliente",
                "Prioridad",
                "Estado",
                "Ticket",
                "SLA",
            ]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._update_actions_state)

        self._load_button = QPushButton("Cargar caso")
        self._load_button.clicked.connect(self._on_load_clicked)
        self._untrack_button = QPushButton("Detener tracking")
        self._untrack_button.clicked.connect(self._on_untrack_clicked)
        self._close_button = QPushButton("Cerrar caso")
        self._close_button.clicked.connect(self._on_close_clicked)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self._load_button)
        buttons_layout.addWidget(self._untrack_button)
        buttons_layout.addWidget(self._close_button)
        buttons_layout.addStretch(1)

        metrics_group = QGroupBox("Métricas")
        self._metrics_labels: dict[str, QLabel] = {
            "total": QLabel("0"),
            "on_track": QLabel("0"),
            "warning": QLabel("0"),
            "overdue": QLabel("0"),
            "reminders": QLabel("—"),
            "closed": QLabel("0"),
        }
        metrics_layout = QFormLayout(metrics_group)
        metrics_layout.addRow("Casos activos", self._metrics_labels["total"])
        metrics_layout.addRow("En SLA", self._metrics_labels["on_track"])
        metrics_layout.addRow("En aviso", self._metrics_labels["warning"])
        metrics_layout.addRow("Fuera de SLA", self._metrics_labels["overdue"])
        metrics_layout.addRow("Recordatorios", self._metrics_labels["reminders"])
        metrics_layout.addRow("Cerrados esta sesión", self._metrics_labels["closed"])

        layout = QVBoxLayout(self)
        self._label = QLabel("Tracking tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Update the placeholder with the active case."""

        summary = case.case_id or case.tracking.ticket_number or "Sin caso seleccionado"
        self._label.setText(f"Tracking tab coming soon\nCaso activo: {summary}")
