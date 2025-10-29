"""Main window implementation for the experimental desktop prototype."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMainWindow, QTabWidget

from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import get_database_root

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


# Backwards compatible alias used by older tests.
MainWindow = KiroshiMainWindow

__all__ = [
    "KiroshiMainWindow",
    "MainWindow",
    "get_database_root",
    "load_global_config",
    "save_global_config",
]
