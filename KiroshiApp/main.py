from __future__ import annotations

from typing import List

from PySide6 import QtCore, QtGui, QtWidgets

from KiroshiApp.state import CaseState, load_autosave, save_autosave
from KiroshiApp.tabs.case import CaseInfoTab
from KiroshiApp.tabs.dashboard import DashboardTab
from KiroshiApp.tabs.debug import DebugTab
from KiroshiApp.tabs.email import EmailTab
from KiroshiApp.tabs.hardware import HardwareTab
from KiroshiApp.tabs.save_load import SaveLoadTab
from KiroshiApp.tabs.settings import SettingsTab
from KiroshiApp.tabs.tables import TablesTab

SECTION_ORDER = [
    "Case",
    "Email",
    "Hardware Issues",
    "Tables",
    "Save/Load",
    "Dashboard",
    "Debug",
    "Settings",
]


class CaseWidget(QtWidgets.QWidget):
    section_map: dict[str, QtWidgets.QWidget]

    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.case = case
        self.sections = QtWidgets.QTabWidget()
        self.sections.setMovable(True)
        self.sections.setTabPosition(QtWidgets.QTabWidget.North)

        self.section_widgets: dict[str, QtWidgets.QWidget] = {}
        self._build_tabs()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.sections)

    def _build_tabs(self) -> None:
        widgets = [
            CaseInfoTab(self.case),
            EmailTab(self.case),
            HardwareTab(self.case),
            TablesTab(self.case),
            SaveLoadTab(self.case),
            DashboardTab(self.case),
            DebugTab(self.case),
            SettingsTab(self.case),
        ]
        for widget, name in zip(widgets, SECTION_ORDER):
            self.section_widgets[name] = widget
            self.sections.addTab(widget, name)

    def copy_active_section(self) -> None:
        widget = self.sections.currentWidget()
        if hasattr(widget, "copy_to_clipboard"):
            if isinstance(widget, CaseInfoTab):
                widget.copy_to_clipboard(widget.summary.toPlainText())
            elif isinstance(widget, EmailTab):
                widget.copy_to_clipboard(widget.template.toPlainText())
            elif isinstance(widget, TablesTab):
                widget.copy_to_clipboard(widget.notes.toPlainText())

    def set_active_section(self, index: int) -> None:
        if 0 <= index < self.sections.count():
            self.sections.setCurrentIndex(index)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kiroshi Desktop")
        self.case_tabs = QtWidgets.QTabWidget()
        self.case_tabs.setTabsClosable(True)
        self.case_tabs.tabCloseRequested.connect(self.close_case)
        self.setCentralWidget(self.case_tabs)
        self.statusBar().showMessage("Ready")
        self.cases: List[CaseState] = []
        self.autosave_timer = QtCore.QTimer(self)
        self.autosave_timer.setInterval(10000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start()

        self.load_cases()
        if not self.cases:
            self.add_case()

        self._install_shortcuts()

    # case management
    def add_case(self, case: CaseState | None = None) -> None:
        case = case or CaseState()
        self.cases.append(case)
        widget = CaseWidget(case)
        idx = self.case_tabs.addTab(widget, case.title)
        self.case_tabs.setCurrentIndex(idx)

    def close_case(self, index: int) -> None:
        if 0 <= index < len(self.cases):
            self.cases.pop(index)
        self.case_tabs.removeTab(index)
        if not self.cases:
            self.add_case()

    def load_cases(self) -> None:
        for case in load_autosave():
            self.add_case(case)

    def autosave(self) -> None:
        save_autosave(self.cases)
        self.statusBar().showMessage("Autosaved", 2000)

    def copy_active_section(self) -> None:
        widget = self.case_tabs.currentWidget()
        if isinstance(widget, CaseWidget):
            widget.copy_active_section()
            self.statusBar().showMessage("Copied active section", 1500)

    def _install_shortcuts(self) -> None:
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Alt+C"), self, self.copy_active_section)
        for idx in range(8):
            QtWidgets.QShortcut(
                QtGui.QKeySequence(f"Ctrl+Alt+{idx+1}"),
                self,
                lambda i=idx: self._activate_section(i),
            )

    def _activate_section(self, index: int) -> None:
        widget = self.case_tabs.currentWidget()
        if isinstance(widget, CaseWidget):
            widget.set_active_section(index)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.autosave()
        return super().closeEvent(event)


def launch() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = MainWindow()
    window.resize(1100, 800)
    window.show()
    app.exec()


if __name__ == "__main__":
    launch()
