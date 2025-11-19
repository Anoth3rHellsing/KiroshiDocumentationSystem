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
from KiroshiApp.core.tracking import (
    TrackedCaseRecord,
    list_tracked_cases,
    stop_tracking,
)


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
        self._second_line_enabled = bool(second_line_enabled)
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
        self._table.setAlternatingRowColors(True)
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

        self._active_case_label = QLabel("Tracking tab coming soon", self)
        self._active_case_label.setWordWrap(True)
        layout.addWidget(self._active_case_label)
        layout.addStretch(1)

        self._reload_records()
        self._update_actions_state()

    def set_second_line_enabled(self, enabled: bool) -> None:
        """Enable or disable tracking actions based on global settings."""

        enabled_flag = bool(enabled)
        if self._second_line_enabled == enabled_flag:
            return
        self._second_line_enabled = enabled_flag
        self._update_actions_state()

    def refresh_case(self, case: CaseData) -> None:
        """Update the placeholder with the active case."""

        summary = self._case_identifier(case)
        self._active_case_label.setText(
            f"Tracking tab coming soon\nCaso activo: {summary}"
        )
        # Highlight the matching tracked case when present.
        identifier = summary
        for row, record in enumerate(self._records):
            if self._case_identifier(record.case) == identifier:
                self._table.selectRow(row)
                break
        else:
            self._table.clearSelection()
        self._update_actions_state()

    def _update_actions_state(self) -> None:
        """Enable or disable controls based on the current selection."""

        has_selection = bool(self._table.selectedIndexes())
        self._load_button.setEnabled(has_selection)

        tracking_actions_enabled = has_selection and self._second_line_enabled
        self._untrack_button.setEnabled(tracking_actions_enabled)
        self._close_button.setEnabled(tracking_actions_enabled)

        # The gate label explains why actions are disabled when second line mode
        # is inactive. Show it only when the user cannot interact with the
        # tracking controls.
        self._gate_label.setVisible(not self._second_line_enabled)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _reload_records(self) -> None:
        """Refresh the table with tracked case information from disk."""

        self._records = list_tracked_cases(base_path=self._base_path)
        self._populate_table()
        self._update_metrics()

    def _populate_table(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.clearContents()
        self._table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            case = record.case
            values = [
                self._case_identifier(case),
                case.company_name or "—",
                case.tracking.priority or "—",
                case.tracking.status or "—",
                case.tracking.ticket_number or "—",
                _sla_status(case.tracking),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, column, item)
        self._table.setSortingEnabled(True)
        self._table.sortItems(0)
        self._table.clearSelection()

    def _update_metrics(self) -> None:
        total = len(self._records)
        on_track = warning = overdue = 0
        for record in self._records:
            status = _sla_status(record.case.tracking)
            if status == "En plazo":
                on_track += 1
            elif status == "Aviso":
                warning += 1
            elif status == "Fuera de plazo":
                overdue += 1

        reminders_enabled = bool(self._reminders_config.get("enabled", False))
        if reminders_enabled:
            times = [
                str(self._reminders_config.get(key) or "")
                for key in ("break_1", "lunch", "break_2")
            ]
            times = [time for time in times if time]
            schedule = " / ".join(times)
            reminders_text = (
                f"Activos ({schedule})" if schedule else "Activos"
            )
            lead_time = self._reminders_config.get("lead_time_minutes")
            if isinstance(lead_time, int) and lead_time > 0:
                reminders_text = f"{reminders_text} · aviso {lead_time} min"
        else:
            reminders_text = "Inactivos"

        self._metrics_labels["total"].setText(str(total))
        self._metrics_labels["on_track"].setText(str(on_track))
        self._metrics_labels["warning"].setText(str(warning))
        self._metrics_labels["overdue"].setText(str(overdue))
        self._metrics_labels["reminders"].setText(reminders_text)
        self._metrics_labels["closed"].setText(str(len(self._closed_cases)))

    def _selected_record(self) -> TrackedCaseRecord | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _case_identifier(self, case: CaseData) -> str:
        return (
            case.case_id
            or case.tracking.ticket_number
            or case.company_name
            or "Sin caso seleccionado"
        )

    def _record_identifier(self, record: TrackedCaseRecord) -> str:
        identifier = self._case_identifier(record.case)
        if identifier == "Sin caso seleccionado":
            identifier = record.path.stem
        return identifier

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def _on_load_clicked(self) -> None:
        record = self._selected_record()
        if not record:
            return
        self.loadRequested.emit(record.case)
        self.refresh_case(record.case)

    def _on_untrack_clicked(self) -> None:
        record = self._selected_record()
        if not record:
            return
        identifier = self._record_identifier(record)
        if self._remove_record(record):
            self.untrackRequested.emit(identifier)

    def _on_close_clicked(self) -> None:
        record = self._selected_record()
        if not record:
            return
        identifier = self._record_identifier(record)
        if self._remove_record(record):
            self._closed_cases.append(identifier)
            self._metrics_labels["closed"].setText(str(len(self._closed_cases)))
            self.closeRequested.emit(identifier)

    def _remove_record(self, record: TrackedCaseRecord) -> bool:
        case_id = record.case.case_id
        removed = False
        if case_id:
            removed = stop_tracking(case_id, base_path=self._base_path)
        if not removed:
            try:
                record.path.unlink()
                removed = True
            except OSError:
                removed = False
        if removed:
            self._reload_records()
            self._update_actions_state()
        return removed
