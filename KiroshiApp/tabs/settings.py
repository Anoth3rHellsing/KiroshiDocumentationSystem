from __future__ import annotations

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class SettingsTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Settings", case, parent)
        self.autosave_checkbox = QtWidgets.QCheckBox("Autosave enabled (10s)")
        self.tooltips_checkbox = QtWidgets.QCheckBox("Show tutorial/tooltips")
        self.autosave_checkbox.setChecked(True)
        self.tooltips_checkbox.setChecked(True)

        layout = QtWidgets.QFormLayout()
        layout.addRow(self.autosave_checkbox)
        layout.addRow(self.tooltips_checkbox)
        self.layout.addLayout(layout)
        self.update_completion(True, "settings")

    def render_state(self, state):
        # settings are global but stored per case for parity
        self.update_completion(state.completed, state.content)
