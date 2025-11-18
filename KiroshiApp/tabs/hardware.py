from __future__ import annotations

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class HardwareTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Hardware Issues", case, parent)
        self.findings = QtWidgets.QPlainTextEdit()
        self.findings.setPlaceholderText("Document hardware tests, screenshots, and attachments")
        self.attachments = QtWidgets.QListWidget()
        self.add_button = QtWidgets.QPushButton("Add attachment")
        self.add_button.clicked.connect(self._add_attachment)
        self.complete_checkbox = QtWidgets.QCheckBox("All diagnostics complete")

        self.layout.addWidget(self.findings)
        self.layout.addWidget(QtWidgets.QLabel("Attachments"))
        self.layout.addWidget(self.attachments)

        footer = QtWidgets.QHBoxLayout()
        footer.addWidget(self.complete_checkbox)
        footer.addWidget(self.add_button)
        footer.addStretch(1)
        self.layout.addLayout(footer)

        self.findings.textChanged.connect(self._update_state)
        self.complete_checkbox.stateChanged.connect(self._update_state)
        self.apply_section_state()

    def _add_attachment(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Add attachment")
        if file_path:
            self.case.attachments.append(file_path)
            self.attachments.addItem(file_path)
            self._update_state()

    def _update_state(self) -> None:
        content = self.findings.toPlainText()
        completed = self.complete_checkbox.isChecked()
        self.update_completion(completed, content)

    def render_state(self, state):
        self.findings.setPlainText(state.content)
        self.complete_checkbox.setChecked(state.completed)
        self.attachments.clear()
        for item in self.case.attachments:
            self.attachments.addItem(item)
