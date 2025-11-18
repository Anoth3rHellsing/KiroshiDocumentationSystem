from __future__ import annotations

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class CaseInfoTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Case", case, parent)
        form = QtWidgets.QFormLayout()
        self.case_id_input = QtWidgets.QLineEdit(case.case_id)
        self.title_input = QtWidgets.QLineEdit(case.title)
        self.summary = QtWidgets.QPlainTextEdit(case.sections.get("Case", {}).content if case.sections else "")

        form.addRow("Case ID", self.case_id_input)
        form.addRow("Title", self.title_input)
        form.addRow("Summary", self.summary)
        self.layout.addLayout(form)

        controls = QtWidgets.QHBoxLayout()
        self.complete_checkbox = QtWidgets.QCheckBox("Mark complete")
        controls.addWidget(self.complete_checkbox)
        copy_btn = QtWidgets.QPushButton("Copy summary")
        copy_btn.clicked.connect(self._copy_summary)
        controls.addWidget(copy_btn)
        controls.addStretch(1)
        self.layout.addLayout(controls)

        self.case_id_input.textChanged.connect(self._update_case_meta)
        self.title_input.textChanged.connect(self._update_case_meta)
        self.summary.textChanged.connect(self._update_case_meta)
        self.complete_checkbox.stateChanged.connect(self._update_case_meta)

        self.apply_section_state()

    def _copy_summary(self) -> None:
        self.copy_to_clipboard(self.summary.toPlainText())

    def _update_case_meta(self) -> None:
        self.case.case_id = self.case_id_input.text()
        self.case.title = self.title_input.text() or "Untitled Case"
        content = self.summary.toPlainText()
        completed = self.complete_checkbox.isChecked()
        self.update_completion(completed, content)

    def render_state(self, state):
        self.summary.setPlainText(state.content)
        self.complete_checkbox.setChecked(state.completed)
