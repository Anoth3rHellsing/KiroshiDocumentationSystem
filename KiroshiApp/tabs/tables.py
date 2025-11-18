from __future__ import annotations

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class TablesTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Tables", case, parent)
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setPlaceholderText("Paste tables copied from Streamlit or Kiroshi exports")
        copy_btn = QtWidgets.QPushButton("Copy to clipboard")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(self.notes.toPlainText()))
        self.complete_checkbox = QtWidgets.QCheckBox("Tables validated")

        self.layout.addWidget(self.notes)
        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(self.complete_checkbox)
        footer.addWidget(copy_btn)
        footer.addStretch(1)
        self.layout.addLayout(footer)

        self.notes.textChanged.connect(self._update_state)
        self.complete_checkbox.stateChanged.connect(self._update_state)
        self.apply_section_state()

    def _update_state(self) -> None:
        self.update_completion(self.complete_checkbox.isChecked(), self.notes.toPlainText())

    def render_state(self, state):
        self.notes.setPlainText(state.content)
        self.complete_checkbox.setChecked(state.completed)
