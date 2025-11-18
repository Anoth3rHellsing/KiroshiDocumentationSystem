from __future__ import annotations

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class EmailTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Email", case, parent)
        self.template = QtWidgets.QPlainTextEdit()
        self.template.setPlaceholderText("Email body or escalation snippet")
        self.complete_checkbox = QtWidgets.QCheckBox("Ready to send")

        copy_btn = QtWidgets.QPushButton("Copy body")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(self.template.toPlainText()))

        self.layout.addWidget(self.template)
        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(self.complete_checkbox)
        footer.addWidget(copy_btn)
        footer.addStretch(1)
        self.layout.addLayout(footer)

        self.template.textChanged.connect(self._update_state)
        self.complete_checkbox.stateChanged.connect(self._update_state)
        self.apply_section_state()

    def _update_state(self) -> None:
        self.update_completion(self.complete_checkbox.isChecked(), self.template.toPlainText())

    def render_state(self, state):
        self.template.setPlainText(state.content)
        self.complete_checkbox.setChecked(state.completed)
