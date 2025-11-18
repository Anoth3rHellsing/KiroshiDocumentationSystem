from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class DebugTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Debug", case, parent)
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.refresh_btn = QtWidgets.QPushButton("Refresh logs")
        self.refresh_btn.clicked.connect(self.refresh)
        self.layout.addWidget(self.log_view)
        self.layout.addWidget(self.refresh_btn)
        self.update_completion(True, "debug")
        self.refresh()

    def refresh(self) -> None:
        log_path = Path("app.log")
        if log_path.exists():
            self.log_view.setPlainText(log_path.read_text(encoding="utf-8"))
        else:
            self.log_view.setPlainText("No logs found yet.")
