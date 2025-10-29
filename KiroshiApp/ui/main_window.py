"""Main window implementation for the experimental desktop prototype."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMainWindow, QTabWidget

from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import get_database_root
from KiroshiApp.core.tracking import start_tracking, stop_tracking

from .case_tab import CaseTab
from .debug_tab import DebugTab
from .email_tab import EmailTab
from .save_load_tab import SaveLoadTab
from .settings_tab import SettingsTab
from .tables_tab import TablesTab
from .tracking_tab import TrackingTab

CONFIG_FILENAME = "settings.json"


def load_global_config(*, base_path: Path | None = None) -> dict[str, Any]:
    """Load the persisted application configuration if available."""

    config_dir = get_database_root(base_path)
    path = config_dir / CONFIG_FILENAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_global_config(config: dict[str, Any], *, base_path: Path | None = None) -> Path:
    """Persist the application configuration to disk."""

    config_dir = get_database_root(base_path)
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / CONFIG_FILENAME
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class KiroshiMainWindow(QMainWindow):
    """Main window that wires together placeholder tabs."""

    def __init__(self, *, case: CaseData | None = None, base_path: Path | None = None) -> None:
        super().__init__()
        self.case = case or CaseData()
        self._config = load_global_config(base_path=base_path)
        self._base_path = base_path
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self.resize(1024, 720)
        self.setCentralWidget(self._build_tabs())

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self)
        self.case_tab = CaseTab(
            self.case,
            second_line_enabled=bool(self._config.get("second_line_mode", False)),
        )
        self.case_tab.startTrackingRequested.connect(self._handle_start_tracking)
        self.case_tab.stopTrackingRequested.connect(self._handle_stop_tracking)
        tabs.addTab(self.case_tab, "Caso")
        tabs.addTab(EmailTab(), "Email")
        tabs.addTab(TablesTab(), "Tablas")
        tabs.addTab(SaveLoadTab(), "Guardar/Cargar")
        self.tracking_tab = TrackingTab(
            base_path=self._base_path,
            reminders_config=self._config.get("wellness_reminders"),
            second_line_enabled=bool(self._config.get("second_line_mode", False)),
        )
        self.tracking_tab.loadRequested.connect(self._handle_load_case_from_tracking)
        self.tracking_tab.untrackRequested.connect(self._handle_stop_tracking)
        self.tracking_tab.closeRequested.connect(self._handle_close_case)
        tabs.addTab(self.tracking_tab, "Control Tower")
        self.settings_tab = SettingsTab(
            config=self._config,
            base_path=self._base_path,
            load_config=load_global_config,
            save_config=save_global_config,
            on_preferences_changed=self._handle_preferences_updated,
        )
        tabs.addTab(self.settings_tab, "Configuración")
        tabs.addTab(DebugTab(), "Debug")
        return tabs

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_preferences_updated(self, config: dict[str, Any]) -> None:
        self._config = dict(config)
        second_line = bool(self._config.get("second_line_mode", False))
        self.case_tab.set_second_line_enabled(second_line)
        self.tracking_tab.set_second_line_enabled(second_line)
        self.tracking_tab.apply_preferences(self._config.get("wellness_reminders"))

    def _handle_start_tracking(self, case: CaseData) -> None:
        if not case.case_id:
            return
        start_tracking(case, base_path=self._base_path)
        self.case = case
        self.case_tab.update_tracking_state(True, case.tracking.status)
        self.tracking_tab.refresh()

    def _handle_stop_tracking(self, case_id: str) -> None:
        if not case_id:
            return
        removed = stop_tracking(case_id, base_path=self._base_path)
        if removed and self.case.case_id == case_id:
            self.case.tracking.active = False
            self.case_tab.update_tracking_state(False, "Sin seguimiento")
        if removed:
            self.tracking_tab.refresh()

    def _handle_close_case(self, case_id: str) -> None:
        if not case_id:
            return
        removed = stop_tracking(case_id, base_path=self._base_path)
        if removed:
            self.tracking_tab.register_closed_case(case_id)
            if self.case.case_id == case_id:
                self.case.tracking.active = False
                self.case.tracking.status = "Cerrado"
                self.case_tab.update_tracking_state(False, "Cerrado")
            self.tracking_tab.refresh()

    def _handle_load_case_from_tracking(self, case: CaseData) -> None:
        self.case = case
        self.case_tab.set_case(case)


# Backwards compatible alias used by older tests.
MainWindow = KiroshiMainWindow

__all__ = [
    "KiroshiMainWindow",
    "MainWindow",
    "get_database_root",
    "load_global_config",
    "save_global_config",
]
