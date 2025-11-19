"""Main window implementation for the experimental desktop prototype."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.ai_client import AIClient
from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import get_database_root, save_autosave, save_case_to_db

from .case_tab import CaseTab
from .debug_tab import DebugTab
from .email_tab import EmailTab
from .chat_window import ChatWindow
from .save_load_tab import SaveLoadTab
from .settings_tab import SettingsTab
from .tables_tab import TablesTab
from .theme import load_stylesheet
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
        self._unavailable_reason: str | None = None
        self._initialise_backend()

    def _initialise_backend(self) -> None:
        try:  # Prefer the Qt-native backend when available.
            from qhotkey import QHotkey  # type: ignore[import-not-found]

            self._qhotkey_class = QHotkey
            self._key_sequence_class = QKeySequence
            self._backend = "qhotkey"
            self._unavailable_reason = None
            return
        except ImportError:
            logging.debug("QHotkey not available; falling back to keyboard module if present.")

        try:
            import keyboard  # type: ignore[import-not-found]

            self._keyboard_module = keyboard
            self._backend = "keyboard"
            self._unavailable_reason = None
        except ImportError:
            logging.warning(
                "Global hotkeys disabled: neither QHotkey nor keyboard modules are installed."
            )
            self._backend = None
            self._unavailable_reason = (
                "Atajos globales deshabilitados: instala qhotkey o keyboard para activarlos."
            )

    @property
    def is_available(self) -> bool:
        return self._backend is not None

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable_reason

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
        self._base_path = base_path
        self._config = load_global_config(base_path=base_path)
        self._ai_client = AIClient()
        self._chat_window: ChatWindow | None = None
        self._save_load_tab: SaveLoadTab | None = None
        self._email_tab: EmailTab | None = None
        self._tables_tab: TablesTab | None = None
        self._tracking_tab: TrackingTab | None = None
        self._settings_tab: SettingsTab | None = None
        self._debug_tab: DebugTab | None = None
        self._autosave_timer = QTimer(self)
        self._hotkey_manager = GlobalHotkeyManager(self)
        self._case_tabs: QTabWidget | None = None
        self._case_dirty: dict[CaseTab, bool] = {}
        self._active_case_for_hotkeys: CaseData | None = None
        self._initial_cases: list[CaseData] = self._load_initial_cases(case)
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self._apply_branding()
        self._apply_theme_preference()
        self.resize(1024, 720)
        self.setCentralWidget(self._build_layout())
        self._init_menus()
        self._init_autosave_timer()
        if getattr(self.active_case, "active_for_hotkeys", False):
            self._active_case_for_hotkeys = self.active_case
        self._refresh_case_dependents(self.active_case)

    def _apply_branding(self) -> None:
        logo_path = Path(__file__).resolve().parents[2] / "Kiroshi_Logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

    def _apply_theme_preference(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        preferred = str(self._config.get("theme", "light") or "light").lower()
        stylesheet = load_stylesheet(preferred)
        if not stylesheet and preferred != "light":
            stylesheet = load_stylesheet("light")
        app.setStyleSheet(stylesheet)

    def _build_layout(self) -> QWidget:
        wrapper = QWidget(self)
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        actions_row = QVBoxLayout()
        new_case_button = QPushButton("Nuevo caso", wrapper)
        new_case_button.clicked.connect(self._handle_new_case_requested)
        actions_row.addWidget(new_case_button)
        layout.addLayout(actions_row)

        self._case_tabs = QTabWidget(wrapper)
        self._case_tabs.setTabsClosable(True)
        self._case_tabs.tabCloseRequested.connect(self._handle_case_tab_close_requested)
        self._case_tabs.currentChanged.connect(self._handle_active_tab_changed)
        layout.addWidget(self._case_tabs)

        self._build_tool_tabs(wrapper)
        layout.addWidget(self._tool_tabs)

        for case_data in self._initial_cases:
            self._add_case_tab(case_data, make_current=False)
        if self._case_tabs.count() == 0:
            self._add_case_tab(CaseData(), make_current=True)
        if self._case_tabs.count():
            self._case_tabs.setCurrentIndex(0)

        return wrapper

    def _build_tool_tabs(self, parent: QWidget) -> None:
        self._tool_tabs = QTabWidget(parent)
        active_case = self._initial_cases[0] if self._initial_cases else CaseData()
        self._email_tab = EmailTab(case=active_case, ai_client=self._ai_client, parent=self)
        self._tool_tabs.addTab(self._email_tab, "Email")
        self._tables_tab = TablesTab(case=active_case, parent=self)
        self._tool_tabs.addTab(self._tables_tab, "Tablas")
        self._save_load_tab = SaveLoadTab(
            case_getter=lambda: self.active_case,
            case_loader=self._handle_case_loaded_from_storage,
            base_path=self._base_path,
        )
        self._tool_tabs.addTab(self._save_load_tab, "Guardar/Cargar")
        self._tracking_tab = TrackingTab(base_path=self._base_path)
        self._tool_tabs.addTab(self._tracking_tab, "Control Tower")
        self._settings_tab = SettingsTab(
            config=self._config,
            base_path=self._base_path,
            load_config=load_global_config,
            save_config=save_global_config,
            on_preferences_changed=self._handle_preferences_updated,
        )
        self._tool_tabs.addTab(self._settings_tab, "Configuración")
        self._debug_tab = DebugTab()
        self._tool_tabs.addTab(self._debug_tab, "Debug")

    def _load_initial_cases(self, explicit_case: CaseData | None) -> list[CaseData]:
        stored_cases: list[CaseData] = []
        raw_cases = self._config.get("open_cases")
        if isinstance(raw_cases, list):
            for payload in raw_cases:
                if isinstance(payload, dict):
                    try:
                        stored_cases.append(CaseData.from_dict(payload))
                    except Exception:
                        continue
        if stored_cases:
            return stored_cases
        if explicit_case:
            return [explicit_case]
        return [CaseData()]

    @property
    def active_case_tab(self) -> CaseTab | None:
        if self._case_tabs is None:
            return None
        widget = self._case_tabs.currentWidget()
        return widget if isinstance(widget, CaseTab) else None

    @property
    def active_case(self) -> CaseData:
        tab = self.active_case_tab
        if tab is not None:
            return tab.case()
        return CaseData()

    def _init_menus(self) -> None:
        menu_bar = self.menuBar()

        archivo_menu = menu_bar.addMenu("Archivo")

        self._new_case_action = QAction("Nuevo caso", self)
        self._new_case_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_case_action.triggered.connect(self._handle_new_case_requested)
        archivo_menu.addAction(self._new_case_action)
        archivo_menu.addSeparator()

        self._save_case_action = QAction("Guardar caso", self)
        self._save_case_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_case_action.triggered.connect(self._save_case_to_database)
        archivo_menu.addAction(self._save_case_action)

        self._save_autosave_action = QAction("Guardar borrador (autosave)", self)
        self._save_autosave_action.triggered.connect(self._trigger_autosave)
        archivo_menu.addAction(self._save_autosave_action)

        archivo_menu.addSeparator()

        exit_action = QAction("Salir", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self._quit_application)
        archivo_menu.addAction(exit_action)

        herramientas_menu = menu_bar.addMenu("Herramientas")

        self._open_chat_action = QAction("Abrir chat IA", self)
        self._open_chat_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        self._open_chat_action.triggered.connect(self._open_chat_window)
        herramientas_menu.addAction(self._open_chat_action)

        menu_bar.addMenu("Ayuda")

    def _add_case_tab(self, case: CaseData, *, make_current: bool = True) -> None:
        if self._case_tabs is None:
            return
        tab = CaseTab(
            case=case,
            parent=self,
            hotkeys_available=self._hotkey_manager.is_available,
            hotkey_unavailable_reason=self._hotkey_manager.unavailable_reason or "",
        )
        tab.caseChanged.connect(lambda updated: self._handle_case_changed(tab, updated))
        tab.hotkeySelectionChanged.connect(
            lambda active: self._handle_hotkey_selection(tab, active)
        )
        index = self._case_tabs.addTab(tab, self._case_tab_title(case, self._case_tabs.count()))
        self._case_dirty[tab] = False
        if make_current:
            self._case_tabs.setCurrentIndex(index)
        self._persist_open_cases()

    def _handle_case_changed(self, tab: CaseTab, case: CaseData) -> None:
        self._case_dirty[tab] = True
        self._update_case_tab_title(tab)
        if tab is self.active_case_tab:
            self._refresh_case_dependents(case)
            self._active_case_for_hotkeys = (
                case if getattr(case, "active_for_hotkeys", False) else None
            )
            try:
                save_autosave(case, base_path=self._base_path)
                self._case_dirty[tab] = False
            except OSError as exc:
                logging.warning("No se pudo guardar el autosave del caso: %s", exc)
        self._persist_open_cases()

    def _handle_hotkey_selection(self, tab: CaseTab, active: bool) -> None:
        if tab is not self.active_case_tab:
            return
        case = tab.case()
        case.active_for_hotkeys = active
        self._active_case_for_hotkeys = case if active else None

    def _handle_active_tab_changed(self, index: int) -> None:  # noqa: ARG002
        case = self.active_case
        self._refresh_case_dependents(case)
        self._active_case_for_hotkeys = (
            case if getattr(case, "active_for_hotkeys", False) else None
        )

    def _handle_new_case_requested(self) -> None:
        self._add_case_tab(CaseData(), make_current=True)

    def _handle_case_loaded_from_storage(self, case: CaseData, source: str) -> None:
        if self._case_tabs is None:
            return
        current_tab = self.active_case_tab
        if current_tab is None:
            self._add_case_tab(case, make_current=True)
            current_tab = self.active_case_tab
        if current_tab is not None:
            current_tab.set_case(case)
            self._case_dirty[current_tab] = False
        self._refresh_case_dependents(case)
        self.statusBar().showMessage(f"Caso cargado desde {source}", 5000)
        self._persist_open_cases()

    def _save_case_to_database(self) -> None:
        case = self.active_case
        try:
            destination = save_case_to_db(case, base_path=self._base_path)
        except OSError as exc:
            logging.warning("No se pudo guardar el caso: %s", exc)
            self.statusBar().showMessage(f"Error al guardar el caso: {exc}", 5000)
            return
        if self._save_load_tab is not None:
            self._save_load_tab.refresh_recent_files()
            self._save_load_tab.refresh_case(case)
        self.statusBar().showMessage(f"Caso guardado en {destination}", 5000)
        tab = self.active_case_tab
        if tab is not None:
            self._case_dirty[tab] = False
        self._persist_open_cases()

    def _trigger_autosave(self) -> None:
        case = self.active_case
        try:
            path = save_autosave(case, base_path=self._base_path)
        except OSError as exc:
            logging.warning("No se pudo crear el autosave: %s", exc)
            self.statusBar().showMessage(f"Error al crear autosave: {exc}", 5000)
            return
        self.statusBar().showMessage(f"Autosave guardado en {path}", 5000)
        tab = self.active_case_tab
        if tab is not None:
            self._case_dirty[tab] = False
        self._persist_open_cases()

    def _open_chat_window(self) -> None:
        if self._chat_window is not None and self._chat_window.isVisible():
            self._chat_window.activateWindow()
            self._chat_window.raise_()
            return
        self._chat_window = ChatWindow(self._ai_client, self.active_case, self)
        self._chat_window.show()

    def _quit_application(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            self.close()

    @property
    def active_case_for_hotkeys(self) -> CaseData | None:
        return self._active_case_for_hotkeys

    def _refresh_case_dependents(self, case: CaseData) -> None:
        self._active_case_for_hotkeys = (
            case if getattr(case, "active_for_hotkeys", False) else None
        )
        if self._tables_tab is not None:
            self._tables_tab.update_case(case)
        if self._email_tab is not None:
            self._email_tab.refresh_case(case)
        if self._save_load_tab is not None:
            self._save_load_tab.refresh_case(case)
        if self._tracking_tab is not None:
            self._tracking_tab.refresh_case(case)
        if self._settings_tab is not None:
            self._settings_tab.refresh_case(case)
        if self._debug_tab is not None:
            self._debug_tab.refresh_case(case)

    def _handle_preferences_updated(self, config: dict[str, Any]) -> None:
        self._config = dict(config)
        self._apply_theme_preference()
        self._persist_open_cases()

    def _init_autosave_timer(self) -> None:
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._handle_autosave_timeout)
        self._autosave_timer.setSingleShot(False)

    def _handle_autosave_timeout(self) -> None:
        if not self.isVisible():  # Avoid writing if the window is closed.
            return
        self._trigger_autosave()

    def showEvent(self, event) -> None:  # type: ignore[override]
        if not self._autosave_timer.isActive():
            self._autosave_timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # type: ignore[override]
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        self._persist_open_cases()
        super().closeEvent(event)

    def _update_case_tab_title(self, tab: CaseTab) -> None:
        if self._case_tabs is None:
            return
        index = self._case_tabs.indexOf(tab)
        if index < 0:
            return
        case = tab.case()
        title = self._case_tab_title(case, index)
        if self._case_dirty.get(tab):
            title += " *"
        self._case_tabs.setTabText(index, title)

    def _case_tab_title(self, case: CaseData, index: int) -> str:
        title = (case.case_id or case.company_name or "").strip()
        if title:
            return title
        return f"Caso {index + 1}"

    def _handle_case_tab_close_requested(self, index: int) -> None:
        if self._case_tabs is None:
            return
        widget = self._case_tabs.widget(index)
        if not isinstance(widget, CaseTab):
            return
        if self._case_dirty.get(widget):
            choice = QMessageBox(self)
            choice.setWindowTitle("Cerrar pestaña")
            choice.setText("El caso tiene cambios sin guardar. ¿Deseas cerrarlo?")
            choice.setStandardButtons(
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            choice.setDefaultButton(QMessageBox.StandardButton.Save)
            result = choice.exec()
            if result == QMessageBox.StandardButton.Cancel:
                return
            if result == QMessageBox.StandardButton.Save:
                self._case_tabs.setCurrentIndex(index)
                self._save_case_to_database()
        self._case_tabs.removeTab(index)
        self._case_dirty.pop(widget, None)
        widget.deleteLater()
        if self._case_tabs.count() == 0:
            self._add_case_tab(CaseData(), make_current=True)
        self._persist_open_cases()

    def _persist_open_cases(self) -> None:
        if self._case_tabs is None:
            return
        cases: list[dict[str, object]] = []
        for idx in range(self._case_tabs.count()):
            tab = self._case_tabs.widget(idx)
            if isinstance(tab, CaseTab):
                try:
                    cases.append(tab.case().to_dict())
                except Exception:
                    continue
        self._config["open_cases"] = cases
        save_global_config(self._config, base_path=self._base_path)


# Backwards compatible alias used by older tests.
MainWindow = KiroshiMainWindow

__all__ = [
    "KiroshiMainWindow",
    "MainWindow",
    "get_database_root",
    "load_global_config",
    "save_global_config",
]
