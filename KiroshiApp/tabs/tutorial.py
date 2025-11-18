from __future__ import annotations

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class TutorialTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Settings", case, parent)
        # Placeholder for contextual tooltips; reuse settings name for shortcuts
        tips = QtWidgets.QLabel(
            "Use Ctrl+Alt+1…8 to jump between tabs and Ctrl+Alt+C to copy the active section."
        )
        tips.setWordWrap(True)
        self.layout.addWidget(tips)
        self.update_completion(True, tips.text())
