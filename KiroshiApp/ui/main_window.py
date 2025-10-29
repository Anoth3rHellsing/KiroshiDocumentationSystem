"""Main window implementation for the experimental desktop prototype."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QTabWidget

from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import get_database_root, save_autosave

from .case_tab import CaseTab
from .debug_tab import DebugTab
from .email_tab import EmailTab
from .save_load_tab import SaveLoadTab
from .settings_tab import SettingsTab
from .tables_tab import TablesTab
from .tracking_tab import TrackingTab

CONFIG_FILENAME = "settings.json"
AUTOSAVE_INTERVAL_MS = 5 * 60 * 1000  # five minutes


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
        self._base_path = base_path
        self._config = load_global_config(base_path=base_path)
        self._status_bar = self.statusBar()
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self.resize(1024, 720)
        self._tabs = self._build_tabs()
        self.setCentralWidget(self._tabs)
        self.refresh_tabs()
        self._setup_autosave()

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self)
        self._case_tab = CaseTab()
        tabs.addTab(self._case_tab, "Caso")
        self._email_tab = EmailTab()
        tabs.addTab(self._email_tab, "Email")
        self._tables_tab = TablesTab()
        tabs.addTab(self._tables_tab, "Tablas")
        self._save_load_tab = SaveLoadTab(
            case_getter=lambda: self.case,
            case_loader=self._apply_loaded_case,
            base_path=self._base_path,
        )
        tabs.addTab(self._save_load_tab, "Guardar/Cargar")
        self._tracking_tab = TrackingTab()
        tabs.addTab(self._tracking_tab, "Control Tower")
        self._settings_tab = SettingsTab()
        tabs.addTab(self._settings_tab, "Configuración")
        self._debug_tab = DebugTab()
        tabs.addTab(self._debug_tab, "Debug")
        return tabs

    def refresh_tabs(self) -> None:
        """Notify all tabs that the case information changed."""

        for index in range(self._tabs.count()):
            widget = self._tabs.widget(index)
            refresh = getattr(widget, "refresh_case", None)
            if callable(refresh):
                refresh(self.case)

    def _apply_loaded_case(self, case: CaseData, source: str) -> None:
        """Update the active case with content loaded from disk."""

        self.case = case
        self.refresh_tabs()
        self._status_bar.showMessage(f"Caso cargado desde {source}", 5000)
        self._perform_autosave(reason="load")

    def notify_case_modified(self, *, reason: str = "manual") -> None:
        """Trigger a refresh and autosave after form edits."""

        self.refresh_tabs()
        self._perform_autosave(reason=reason)

    def _setup_autosave(self) -> None:
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._on_autosave_timeout)
        self._autosave_timer.start()
        self._perform_autosave(reason="inicio")

    def _on_autosave_timeout(self) -> None:
        self._perform_autosave(reason="temporizador")

    def _perform_autosave(self, *, reason: str) -> None:
        try:
            path = save_autosave(self.case, base_path=self._base_path)
        except OSError as exc:  # pragma: no cover - filesystem errors are rare
            self._status_bar.showMessage(f"Autosave falló: {exc}", 5000)
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._status_bar.showMessage(f"Autosave ({reason}) {timestamp} → {path}", 5000)


# Backwards compatible alias used by older tests.
MainWindow = KiroshiMainWindow

__all__ = [
    "KiroshiMainWindow",
    "MainWindow",
    "get_database_root",
    "load_global_config",
    "save_global_config",
]
