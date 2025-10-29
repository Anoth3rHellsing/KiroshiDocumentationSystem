"""Tracking tab that surfaces TrackedCases information."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.model import CaseData
from ..core.tracking import list_tracked_cases, update_tracked_case

LOGGER = logging.getLogger(__name__)


class TrackingTab(QWidget):
    """Display and edit tracked cases stored on disk."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Case ID", "Compañía", "Estado", "Prioridad", "Actualizado"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.cellChanged.connect(self._on_cell_changed)
        self._updating = False
        self._has_loaded = False

        self._summary_label = QLabel()
        self._summary_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._build_ui()

    def showEvent(self, event: QEvent) -> None:  # pragma: no cover - UI dispatch
        super().showEvent(event)
        self.ensure_loaded()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._summary_label)
        layout.addWidget(self._table)

        button_row = QHBoxLayout()
        close_button = QPushButton("Marcar como cerrado")
        close_button.clicked.connect(self._close_selected)
        button_row.addWidget(close_button)

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.refresh)
        button_row.addWidget(refresh_button)

        button_row.addStretch()
        layout.addLayout(button_row)

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        records = list_tracked_cases()
        self._table.setRowCount(len(records))
        self._updating = True
        try:
            for row, record in enumerate(records):
                self._set_item(row, 0, record.case.case_id or "—", editable=False)
                self._set_item(row, 1, record.case.company_name or "—", editable=False)
                status = record.case.tracking.status if isinstance(record.case, CaseData) else ""
                self._set_item(row, 2, status or "En progreso")
                priority = record.case.tracking.priority if record.case.tracking else ""
                self._set_item(row, 3, priority or "Normal")
                self._set_item(row, 4, record.last_modified or "")
                self._table.item(row, 0).setData(Qt.UserRole, str(record.path))
        finally:
            self._updating = False
        self._update_summary([record.case for record in records])
        self._table.resizeColumnsToContents()
        self._has_loaded = True

    def ensure_loaded(self) -> None:
        if not self._has_loaded:
            self.refresh()

    def _set_item(self, row: int, column: int, value: str, *, editable: bool = True) -> None:
        item = QTableWidgetItem(value)
        if not editable:
            item.setFlags(item.flags() ^ Qt.ItemIsEditable)
        self._table.setItem(row, column, item)

    def _on_cell_changed(self, row: int, column: int) -> None:
        if self._updating:
            return
        path_item = self._table.item(row, 0)
        if not path_item:
            return
        path_text = path_item.data(Qt.UserRole)
        if not path_text:
            return
        path = Path(path_text)
        status_item = self._table.item(row, 2)
        priority_item = self._table.item(row, 3)
        try:
            update_tracked_case(
                path,
                tracking_updates={
                    "status": status_item.text() if status_item else "",
                    "priority": priority_item.text() if priority_item else "",
                },
            )
        except Exception as exc:  # pragma: no cover - defensive path
            LOGGER.error("Failed to update tracked case: %s", exc)
            QMessageBox.warning(self, "Tracking", f"No se pudo actualizar el caso: {exc}")
            self.refresh()

    def _close_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Tracking", "Selecciona un caso")
            return
        item = self._table.item(row, 0)
        if not item:
            return
        path = item.data(Qt.UserRole)
        if not path:
            return
        try:
            update_tracked_case(path, tracking_updates={"active": False, "status": "Closed"})
        except Exception as exc:
            LOGGER.error("Failed to close tracked case: %s", exc)
            QMessageBox.warning(self, "Tracking", f"No se pudo cerrar el caso: {exc}")
            return
        self.refresh()

    def _update_summary(self, cases: list[CaseData]) -> None:
        dell_count = sum(1 for case in cases if _contains(case, "dell"))
        fedex_count = sum(1 for case in cases if _contains(case, "fedex"))
        sla_count = sum(1 for case in cases if _is_sla_soon(case))
        self._summary_label.setText(
            f"Dell: {dell_count} | FedEx: {fedex_count} | SLA próximos: {sla_count}"
        )


def _contains(case: CaseData, keyword: str) -> bool:
    haystack = " ".join(
        [
            case.company_name or "",
            case.brief_description or "",
            case.description or "",
            case.additional_info or "",
        ]
    ).lower()
    return keyword in haystack


def _is_sla_soon(case: CaseData) -> bool:
    try:
        raw = case.tracking.expected_arrival_date if case.tracking else ""
    except AttributeError:
        raw = ""
    if not raw:
        return False
    try:
        date = datetime.fromisoformat(raw)
    except ValueError:
        return False
    return 0 <= (date - datetime.utcnow()).days <= 3
