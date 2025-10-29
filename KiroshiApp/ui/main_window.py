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
        self._base_path = base_path
        self._config = load_global_config(base_path=base_path)
        self._ai_client = AIClient()
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self.resize(1024, 720)
        self.setCentralWidget(self._build_tabs())
        self._init_menus()

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget(self)
        tabs.addTab(CaseTab(), "Caso")
        tabs.addTab(EmailTab(self.case, self._ai_client), "Email")
        tabs.addTab(TablesTab(), "Tablas")
        tabs.addTab(SaveLoadTab(), "Guardar/Cargar")
        tabs.addTab(TrackingTab(), "Control Tower")
        tabs.addTab(SettingsTab(), "Configuración")
        tabs.addTab(DebugTab(), "Debug")
        return tabs

    def _init_menus(self) -> None:
        menu_bar = self.menuBar()
        hotkey_menu = menu_bar.addMenu("Hotkeys")
        action = QAction("Use this case for global clipboard hotkeys", self)
        action.setCheckable(True)
        action.toggled.connect(self._toggle_case_hotkeys)
        hotkey_menu.addAction(action)
        self._hotkey_action = action
        if not self._hotkey_manager.is_available:
            action.setEnabled(False)
            action.setToolTip(
                "Global hotkeys are unavailable because QHotkey and keyboard modules are missing."
            )

    def _toggle_case_hotkeys(self, enabled: bool) -> None:
        if not self._hotkey_manager.is_available:
            return
        self._use_case_for_hotkeys = enabled
        if enabled:
            self._register_case_hotkeys()
            self.statusBar().showMessage(
                "Global hotkeys active for this case", 3000
            )
        else:
            self._hotkey_manager.unregister_all()
            self.statusBar().showMessage("Global hotkeys disabled", 3000)

    def _register_case_hotkeys(self) -> None:
        self._hotkey_manager.unregister_all()
        sequences: Iterable[str] = self.HOTKEY_SEQUENCES
        for index, sequence in enumerate(sequences):
            if self._tables_tab.section_at(index) is None:
                break
            self._hotkey_manager.register(sequence, self._make_section_callback(index))
        self._hotkey_manager.register("ctrl+alt+c", self._copy_all_sections)

    def _make_section_callback(self, index: int) -> Callable[[], None]:
        def _callback() -> None:
            self._copy_section(index)

        return _callback

    def _copy_section(self, index: int) -> None:
        content = self._tables_tab.section_tsv(index)
        if not content:
            return
        QApplication.clipboard().setText(content)
        self.statusBar().showMessage(
            f"Copied table {index + 1} to clipboard", 3000
        )

    def _copy_all_sections(self) -> None:
        content = self._tables_tab.all_sections_tsv()
        if not content:
            return
        QApplication.clipboard().setText(content)
        self.statusBar().showMessage("Copied all tables to clipboard", 3000)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._hotkey_manager.unregister_all()
        super().closeEvent(event)


# Backwards compatible alias used by older tests.
MainWindow = KiroshiMainWindow

__all__ = [
    "KiroshiMainWindow",
    "MainWindow",
    "get_database_root",
    "load_global_config",
    "save_global_config",
]
