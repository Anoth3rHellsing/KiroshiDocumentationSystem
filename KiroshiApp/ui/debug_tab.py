"""Debug tab placeholder for the experimental desktop prototype."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from KiroshiApp.core.model import CaseData


class DebugTab(QWidget):
    """Simple placeholder widget until the real implementation arrives."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._label = QLabel("Debug tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Show debugging information for the active case."""

        summary = case.case_id or case.last_modified or "Sin caso seleccionado"
        self._label.setText(f"Debug tab coming soon\nCaso activo: {summary}")
