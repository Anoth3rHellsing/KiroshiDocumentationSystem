"""Settings tab placeholder for the experimental desktop prototype."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from KiroshiApp.core.model import CaseData


class SettingsTab(QWidget):
    """Simple placeholder widget until the real implementation arrives."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._label = QLabel("Settings tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Echo the active case identifier."""

        summary = case.case_id or case.company_name or "Sin caso seleccionado"
        self._label.setText(f"Settings tab coming soon\nCaso activo: {summary}")
