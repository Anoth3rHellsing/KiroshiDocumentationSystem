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
        layout.addWidget(self._header_label)
        layout.addWidget(self._gate_label)
        layout.addWidget(self._table)
        layout.addLayout(buttons_layout)
        layout.addWidget(metrics_group)
        layout.addStretch(1)

        self.set_second_line_enabled(second_line_enabled)
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload tracked case information from disk."""

        self._records = list_tracked_cases(base_path=self._base_path)
        self._table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            case = record.case
            tracking = case.tracking if isinstance(case.tracking, TrackingData) else TrackingData()
            values = [
                case.case_id or "(sin ID)",
                case.company_name or "(sin cliente)",
                tracking.priority or "Normal",
                tracking.status or "", 
                tracking.ticket_number or "",
                _sla_status(tracking),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, record.case.case_id)
                self._table.setItem(row, column, item)

        self._update_metrics()
        self._update_actions_state()

    def set_second_line_enabled(self, enabled: bool) -> None:
        """Enable or disable interactions based on 2nd Line mode."""

        self._gate_label.setVisible(not enabled)
        self._table.setEnabled(enabled)
        self._load_button.setEnabled(enabled and bool(self._records))
        self._untrack_button.setEnabled(False)
        self._close_button.setEnabled(False)
        self._update_actions_state()

    def apply_preferences(self, reminders_config: dict[str, Any] | None) -> None:
        """Update reminder preferences displayed in the metrics panel."""

        self._reminders_config = reminders_config or {}
        self._update_metrics()

    def register_closed_case(self, case_id: str) -> None:
        """Track locally closed cases for the session metrics."""

        if case_id and case_id not in self._closed_cases:
            self._closed_cases.append(case_id)
        self._update_metrics()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _current_record(self) -> TrackedCaseRecord | None:
        indexes = self._table.selectionModel().selectedRows() if self._table.selectionModel() else []
        if not indexes:
            return None
        row = indexes[0].row()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def _update_actions_state(self) -> None:
        record = self._current_record()
        enabled = bool(record)
        if not self._table.isEnabled():
            enabled = False
        self._load_button.setEnabled(enabled)
        self._untrack_button.setEnabled(enabled)
        self._close_button.setEnabled(enabled)

    def _update_metrics(self) -> None:
        total = len(self._records)
        on_track = 0
        warning = 0
        overdue = 0
        for record in self._records:
            status = _sla_status(record.case.tracking)
            if status == "En plazo":
                on_track += 1
            elif status == "Aviso":
                warning += 1
            elif status == "Fuera de plazo":
                overdue += 1

        reminders_enabled = False
        lead = ""
        if isinstance(self._reminders_config, dict):
            reminders_enabled = bool(self._reminders_config.get("enabled", False))
            if reminders_enabled:
                lead_value = self._reminders_config.get("notification_lead", "")
                if lead_value:
                    lead = f"{lead_value} min antes"

        self._metrics_labels["total"].setText(str(total))
        self._metrics_labels["on_track"].setText(str(on_track))
        self._metrics_labels["warning"].setText(str(warning))
        self._metrics_labels["overdue"].setText(str(overdue))
        self._metrics_labels["closed"].setText(str(len(self._closed_cases)))
        if reminders_enabled:
            self._metrics_labels["reminders"].setText(f"Activos ({lead or 'sin adelanto'})")
        else:
            self._metrics_labels["reminders"].setText("Desactivados")

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------
    def _on_load_clicked(self) -> None:
        record = self._current_record()
        if record:
            self.loadRequested.emit(record.case)

    def _on_untrack_clicked(self) -> None:
        record = self._current_record()
        if record:
            self.untrackRequested.emit(record.case.case_id)

    def _on_close_clicked(self) -> None:
        record = self._current_record()
        if record:
            self.closeRequested.emit(record.case.case_id)
