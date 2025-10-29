"""Tracking tab placeholder for the experimental desktop prototype."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from KiroshiApp.core.model import CaseData


class TrackingTab(QWidget):
    """Simple placeholder widget until the real implementation arrives."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._label = QLabel("Tracking tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Update the placeholder with the active case."""

        summary = case.case_id or case.tracking.ticket_number or "Sin caso seleccionado"
        self._label.setText(f"Tracking tab coming soon\nCaso activo: {summary}")
