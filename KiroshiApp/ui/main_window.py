"""Minimal main window for the experimental desktop prototype."""
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from .case_tab import CaseTab
from .debug_tab import DebugTab
from .email_tab import EmailTab
from .save_load_tab import SaveLoadTab
from .settings_tab import SettingsTab
from .tables_tab import TablesTab
from .tracking_tab import TrackingTab


class MainWindow(QMainWindow):
    """Main window that wires together placeholder tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self.resize(1024, 720)
        self.setCentralWidget(self._build_tabs())

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self)
        tabs.addTab(CaseTab(), "Caso")
        tabs.addTab(EmailTab(), "Email")
        tabs.addTab(TablesTab(), "Tablas")
        tabs.addTab(SaveLoadTab(), "Guardar/Cargar")
        tabs.addTab(TrackingTab(), "Control Tower")
        tabs.addTab(SettingsTab(), "Configuración")
        tabs.addTab(DebugTab(), "Debug")
        return tabs
