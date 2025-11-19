"""Main window implementation for the experimental desktop prototype."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolButton,
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


@dataclass
class CaseTabPage:
    """Container for a single case and its associated tabs."""

    widget: QWidget
    case_tab: CaseTab
    email_tab: EmailTab
    tables_tab: TablesTab
    save_load_tab: SaveLoadTab
    tracking_tab: TrackingTab
    settings_tab: SettingsTab
    debug_tab: DebugTab
    case: CaseData
    dirty: bool = False


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
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self._tabs.currentChanged.connect(self._handle_tab_changed)
        self._active_case_for_hotkeys: CaseData | None = None
        self._tab_counter = 1
        self._pages: dict[QWidget, CaseTabPage] = {}
        self._autosave_timer = QTimer(self)
        self._hotkey_manager = GlobalHotkeyManager(self)
        self.setWindowTitle("Kiroshi Desktop Prototype")
        self._apply_branding()
        self._apply_theme_preference()
        self.resize(1024, 720)
        self._create_new_case_tab(case or CaseData(), select=True)
        self._add_new_case_button()
        self.setCentralWidget(self._tabs)
        self._init_menus()
        self._init_autosave_timer()

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

    def _add_new_case_button(self) -> None:
        button = QToolButton(self)
        button.setText("+ Nuevo caso")
        button.clicked.connect(lambda: self._create_new_case_tab(CaseData(), select=True))
        self._tabs.setCornerWidget(button)

    def _create_case_page(self, case: CaseData) -> CaseTabPage:
        container = QWidget(self._tabs)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget(container)
        layout.addWidget(tabs)

        case_tab = CaseTab(
            case=case,
            parent=container,
            hotkeys_available=self._hotkey_manager.is_available,
            hotkey_unavailable_reason=self._hotkey_manager.unavailable_reason or "",
        )
        case_tab.caseChanged.connect(lambda updated: self._handle_case_changed(container, updated))
        case_tab.hotkeySelectionChanged.connect(
            lambda active: self._handle_hotkey_selection(container, active)
        )
        tabs.addTab(case_tab, "Caso")

        email_tab = EmailTab(case=case, ai_client=self._ai_client, parent=container)
        tabs.addTab(email_tab, "Email")

        tables_tab = TablesTab(case=case, parent=container)
        tabs.addTab(tables_tab, "Tablas")

        save_load_tab = SaveLoadTab(
            case_getter=case_tab.case,
            case_loader=self._handle_case_loaded_from_storage,
            base_path=self._base_path,
        )
        tabs.addTab(save_load_tab, "Guardar/Cargar")

        tracking_tab = TrackingTab(base_path=self._base_path)
        tabs.addTab(tracking_tab, "Control Tower")

        settings_tab = SettingsTab(
            config=self._config,
            base_path=self._base_path,
            load_config=load_global_config,
            save_config=save_global_config,
            on_preferences_changed=self._handle_preferences_updated,
        )
        tabs.addTab(settings_tab, "Configuración")

        debug_tab = DebugTab()
        tabs.addTab(debug_tab, "Debug")

        return CaseTabPage(
            widget=container,
            case_tab=case_tab,
            email_tab=email_tab,
            tables_tab=tables_tab,
            save_load_tab=save_load_tab,
            tracking_tab=tracking_tab,
            settings_tab=settings_tab,
            debug_tab=debug_tab,
            case=case,
        )

    def _create_new_case_tab(self, case: CaseData, *, select: bool = False) -> None:
        page = self._create_case_page(case)
        label = self._tab_label_for_case(page.case)
        self._pages[page.widget] = page
        index = self._tabs.addTab(page.widget, label)
        if select or self._tabs.count() == 1:
            self._tabs.setCurrentIndex(index)
            self._handle_tab_changed(self._tabs.currentIndex())
        self._refresh_case_dependents(page)

    def _init_menus(self) -> None:
        menu_bar = self.menuBar()

        archivo_menu = menu_bar.addMenu("Archivo")

        new_case_action = QAction("Nuevo caso", self)
        new_case_action.setShortcut(QKeySequence("Ctrl+N"))
        new_case_action.triggered.connect(lambda: self._create_new_case_tab(CaseData(), select=True))
        archivo_menu.addAction(new_case_action)

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

    def _handle_case_changed(self, widget: QWidget, case: CaseData) -> None:
        page = self._pages.get(widget)
        if page is None:
            return
        page.case = case
        page.dirty = True
        self._refresh_case_dependents(page)
        self._update_tab_label(page)
        try:
            save_autosave(case, base_path=self._base_path)
        except OSError as exc:
            logging.warning("No se pudo guardar el autosave del caso: %s", exc)

    def _handle_hotkey_selection(self, widget: QWidget, active: bool) -> None:
        page = self._pages.get(widget)
        if page is None:
            return
        page.case.active_for_hotkeys = active
        self._active_case_for_hotkeys = page.case if active else None

    def _handle_case_loaded_from_storage(self, case: CaseData, source: str) -> None:
        self._create_new_case_tab(case, select=True)
        self.statusBar().showMessage(f"Caso cargado desde {source}", 5000)

    def _save_case_to_database(self) -> None:
        page = self._current_page
        if page is None:
            return
        try:
            destination = save_case_to_db(page.case, base_path=self._base_path)
        except OSError as exc:
            logging.warning("No se pudo guardar el caso: %s", exc)
            self.statusBar().showMessage(f"Error al guardar el caso: {exc}", 5000)
            return
        page.save_load_tab.refresh_recent_files()
        page.save_load_tab.refresh_case(page.case)
        page.dirty = False
        self._update_tab_label(page)
        self.statusBar().showMessage(f"Caso guardado en {destination}", 5000)

    def _trigger_autosave(self) -> None:
        page = self._current_page
        if page is None:
            return
        try:
            path = save_autosave(page.case, base_path=self._base_path)
        except OSError as exc:
            logging.warning("No se pudo crear el autosave: %s", exc)
            self.statusBar().showMessage(f"Error al crear autosave: {exc}", 5000)
            return
        page.dirty = False
        self._update_tab_label(page)
        self.statusBar().showMessage(f"Autosave guardado en {path}", 5000)

    def _open_chat_window(self) -> None:
        page = self._current_page
        if page is None:
            return
        if self._chat_window is not None and self._chat_window.isVisible():
            self._chat_window.activateWindow()
            self._chat_window.raise_()
            return
        self._chat_window = ChatWindow(self._ai_client, page.case_tab.case, self)
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

    @property
    def _current_page(self) -> CaseTabPage | None:
        widget = self._tabs.currentWidget()
        if widget is None:
            return None
        return self._pages.get(widget)

    def _tab_label_for_case(self, case: CaseData, *, dirty: bool | None = None) -> str:
        name = case.case_id.strip() or case.company_name.strip() or case.brief_description.strip()
        if not name:
            name = f"Caso {self._tab_counter}"
            self._tab_counter += 1
        suffix = " *" if dirty else ""
        return f"{name}{suffix}"

    def _update_tab_label(self, page: CaseTabPage) -> None:
        index = self._tabs.indexOf(page.widget)
        if index == -1:
            return
        label = self._tab_label_for_case(page.case, dirty=page.dirty)
        self._tabs.setTabText(index, label)

    def _refresh_case_dependents(self, page: CaseTabPage) -> None:
        case = page.case
        self._active_case_for_hotkeys = case if getattr(case, "active_for_hotkeys", False) else None
        page.tables_tab.update_case(case)
        page.email_tab.refresh_case(case)
        page.save_load_tab.refresh_case(case)
        page.tracking_tab.refresh_case(case)
        page.settings_tab.refresh_case(case)
        page.debug_tab.refresh_case(case)

    def _handle_preferences_updated(self, config: dict[str, Any]) -> None:
        self._config = dict(config)
        self._apply_theme_preference()

    def _handle_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        page = self._pages.get(widget) if widget is not None else None
        case = page.case if page else None
        self._active_case_for_hotkeys = case if getattr(case, "active_for_hotkeys", False) else None

    def _close_tab(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if widget is None:
            return
        page = self._pages.get(widget)
        if page is not None and page.dirty:
            reply = QMessageBox.question(
                self,
                "Cerrar pestaña",
                "Hay cambios sin guardar en este caso. ¿Deseas cerrar la pestaña?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self._pages.pop(widget, None)
        self._tabs.removeTab(index)
        widget.deleteLater()
        if self._tabs.count() == 0:
            self._create_new_case_tab(CaseData(), select=True)

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
