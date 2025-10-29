"""Main window implementation for the experimental desktop prototype."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QAction, QApplication, QMainWindow, QTabWidget

from KiroshiApp.core.ai_client import AIClient
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


class GlobalHotkeyManager:
    """Register global shortcuts using QHotkey or keyboard."""

    def __init__(self, parent: QMainWindow) -> None:
        self._parent = parent
        self._backend: str | None = None
        self._hotkeys: list[object] = []
        self._keyboard_module: Any | None = None
        self._qhotkey_class: Any | None = None
        self._key_sequence_class: Any | None = None
        self._initialise_backend()

    def _initialise_backend(self) -> None:
        try:  # Prefer the Qt-native backend when available.
            from qhotkey import QHotkey  # type: ignore[import-not-found]

            self._qhotkey_class = QHotkey
            self._key_sequence_class = QKeySequence
            self._backend = "qhotkey"
            return
        except ImportError:
            logging.debug("QHotkey not available; falling back to keyboard module if present.")

        try:
            import keyboard  # type: ignore[import-not-found]

            self._keyboard_module = keyboard
            self._backend = "keyboard"
        except ImportError:
            logging.warning(
                "Global hotkeys disabled: neither QHotkey nor keyboard modules are installed."
            )
            self._backend = None

    @property
    def is_available(self) -> bool:
        return self._backend is not None

    def register(self, sequence: str, callback: Callable[[], None]) -> None:
        if self._backend == "qhotkey":
            assert self._qhotkey_class is not None and self._key_sequence_class is not None
            hotkey = self._qhotkey_class(self._key_sequence_class(sequence), parent=self._parent)
            hotkey.activated.connect(callback)  # type: ignore[no-untyped-call]
            if not hotkey.setRegistered(True):
                logging.warning("Failed to register global hotkey: %s", sequence)
                hotkey.deleteLater()
                return
            self._hotkeys.append(hotkey)
        elif self._backend == "keyboard":
            try:
                handler = self._keyboard_module.add_hotkey(sequence, callback)
            except Exception as exc:  # pragma: no cover - platform dependent
                logging.warning("Failed to register keyboard hotkey %s: %s", sequence, exc)
                return
            self._hotkeys.append(handler)

    def unregister_all(self) -> None:
        if self._backend == "qhotkey":
            while self._hotkeys:
                hotkey = self._hotkeys.pop()
                try:
                    hotkey.setRegistered(False)
                finally:
                    hotkey.deleteLater()
        elif self._backend == "keyboard":
            while self._hotkeys:
                handler = self._hotkeys.pop()
                try:
                    self._keyboard_module.remove_hotkey(handler)
                except KeyError:
                    pass


class KiroshiMainWindow(QMainWindow):
    """Main window that wires together placeholder tabs."""

    HOTKEY_SEQUENCES = (
        "ctrl+alt+1",
        "ctrl+alt+2",
        "ctrl+alt+3",
        "ctrl+alt+4",
        "ctrl+alt+5",
        "ctrl+alt+6",
        "ctrl+alt+7",
        "ctrl+alt+8",
    )

    def __init__(self, *, case: CaseData | None = None, base_path: Path | None = None) -> None:
        super().__init__()
        self.case = case or CaseData()
        self._active_case_for_hotkeys: CaseData | None = (
            self.case if getattr(self.case, "active_for_hotkeys", False) else None
        )
        self._base_path = base_path
        self._loaded_case_source: str | None = None
        self._config = load_global_config(base_path=base_path)
        self._ai_client = AIClient()
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self.resize(1024, 720)
        self.setCentralWidget(self._build_tabs())
        self._init_menus()

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self)
        self._case_tab = CaseTab(case=self.case, parent=self)
        self._case_tab.caseChanged.connect(self._handle_case_changed)
        self._case_tab.hotkeySelectionChanged.connect(self._handle_hotkey_selection)
        tabs.addTab(self._case_tab, "Caso")
        self._email_tab = EmailTab(self.case, self._ai_client, self)
        tabs.addTab(self._email_tab, "Email")
        self._tables_tab = TablesTab(case=self.case, parent=self)
        tabs.addTab(self._tables_tab, "Tablas")
        self._save_load_tab = SaveLoadTab(
            self._get_active_case,
            self._load_case_from_disk,
            base_path=self._base_path,
        )
        tabs.addTab(self._save_load_tab, "Guardar/Cargar")
        self._tracking_tab = TrackingTab(base_path=self._base_path)
        tabs.addTab(self._tracking_tab, "Control Tower")
        self._settings_tab = SettingsTab(
            config=self._config,
            base_path=self._base_path,
            load_config=load_global_config,
            save_config=save_global_config,
        )
        tabs.addTab(self._settings_tab, "Configuración")
        self._debug_tab = DebugTab()
        tabs.addTab(self._debug_tab, "Debug")
        return tabs

    def _get_active_case(self) -> CaseData:
        return self.case

    def _load_case_from_disk(self, case: CaseData, source: str) -> None:
        self.case = case
        self._loaded_case_source = source
        self._case_tab.set_case(case)
        self._refresh_case_dependents(case)

    def _handle_case_changed(self, case: CaseData) -> None:
        self.case = case
        self._refresh_case_dependents(case)

    def _handle_hotkey_selection(self, active: bool) -> None:
        self.case.active_for_hotkeys = active
        self._active_case_for_hotkeys = self.case if active else None

    @property
    def active_case_for_hotkeys(self) -> CaseData | None:
        return self._active_case_for_hotkeys

    def _refresh_case_dependents(self, case: CaseData) -> None:
        self._active_case_for_hotkeys = (
            case if getattr(case, "active_for_hotkeys", False) else None
        )
        self._tables_tab.update_case(case)
        self._email_tab.refresh_case(case)
        self._save_load_tab.refresh_case(case)
        self._tracking_tab.refresh_case(case)
        self._settings_tab.refresh_case(case)
        self._debug_tab.refresh_case(case)


# Backwards compatible alias used by older tests.
MainWindow = KiroshiMainWindow

__all__ = [
    "KiroshiMainWindow",
    "MainWindow",
    "get_database_root",
    "load_global_config",
    "save_global_config",
]
