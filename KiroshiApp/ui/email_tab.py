"""Email tab placeholder for the experimental desktop prototype."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from KiroshiApp.core.model import CaseData


class EmailTab(QWidget):
    """Simple placeholder widget until the real implementation arrives."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._label = QLabel("Email tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Display basic context about the selected case."""

        summary = case.case_id or case.email or "Sin caso seleccionado"
        self._label.setText(f"Email tab coming soon\nCaso activo: {summary}")
