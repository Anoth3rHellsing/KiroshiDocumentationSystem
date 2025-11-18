from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from KiroshiApp.state import CaseState, SectionState


class BaseSectionWidget(QtWidgets.QWidget):
    section_changed = QtCore.Signal(str, SectionState)

    def __init__(self, section_name: str, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.section_name = section_name
        self.case = case
        self.status_label = QtWidgets.QLabel("Incomplete")
        self.status_label.setStyleSheet("color: #c0392b;")
        self.layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel(f"{section_name} Section"))
        header.addStretch(1)
        header.addWidget(self.status_label)
        self.layout.addLayout(header)

    def update_completion(self, completed: bool, content: str | None = None) -> None:
        state = self.case.ensure_section(self.section_name)
        state.completed = completed
        if content is not None:
            state.content = content
        self.status_label.setText("Complete" if completed else "Incomplete")
        self.status_label.setStyleSheet("color: #27ae60;" if completed else "color: #c0392b;")
        self.section_changed.emit(self.section_name, state)

    def apply_section_state(self) -> None:
        state = self.case.ensure_section(self.section_name)
        self.render_state(state)
        self.update_completion(state.completed, state.content)

    def render_state(self, state: SectionState) -> None:
        """Allow subclasses to rehydrate from stored content."""
        # default is no-op; override where needed
        _ = state

    def copy_to_clipboard(self, text: str) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
