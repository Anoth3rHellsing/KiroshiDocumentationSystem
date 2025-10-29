"""Main window wiring together all desktop tabs."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.ai_client import AIClient
from ..core.attachments import iter_attachments
from ..core.model import CaseData
from ..core.pdf_generator import generate_case_pdf
from ..core.storage import save_autosave, save_case_to_db
from ..core.tracking import start_tracking, stop_tracking
from ..core.utils import get_database_root, load_global_config, save_global_config, utc_now_iso
from .case_tab import CaseTab
from .chat_window import ChatWindow
from .debug_tab import DebugTab
from .email_tab import EmailTab
from .save_load_tab import SaveLoadTab
from .settings_tab import SettingsTab
from .tracking_tab import TrackingTab

LOGGER = logging.getLogger(__name__)


class KiroshiMainWindow(QMainWindow):
    """Top level PySide6 window for the experimental desktop app."""

    def __init__(
        self,
        *,
        case: CaseData | None = None,
        ai_client: AIClient | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = load_global_config()
        self._autosave_to_db_enabled = bool(self._config.get("autosave_to_db", True))
        self._ai_client = ai_client or AIClient()
        self._apply_ai_settings(self._config.get("ai", {}))

        self._case_tab = CaseTab(case)
        self._email_tab = EmailTab(self._case_tab.current_case, self._ai_client)
        self._tracking_tab = TrackingTab()
        self._settings_tab = SettingsTab(
            self._on_autosave_changed,
            self._on_ai_settings_changed,
        )
        self._debug_tab = DebugTab()
        self._save_load_tab = SaveLoadTab(
            self._case_tab.current_case,
            self._set_case,
            autosave_toggle=self._case_tab.set_autosave_enabled,
            autosave_db_enabled=self._autosave_to_db_enabled,
            on_autosave_db_changed=self._on_autosave_db_changed,
        )

        self._chat_window: ChatWindow | None = None

        self._tab_widget = QTabWidget()
        self._build_ui()

        self._case_tab.on_manual_autosave(self._on_autosave_completed)
        self._case_tab.on_tracking_toggled(self._on_track_case)

    def _build_ui(self) -> None:
        self.setWindowTitle("Kiroshi Desktop Experimental")
        self.resize(1200, 720)
        self._install_menu_bar()
        self._configure_status_bar()

        logo_path = Path(__file__).resolve().parent.parent / "assets" / "icons" / "kiroshi_logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        self._tab_widget.addTab(self._case_tab, "Caso")
        self._tab_widget.addTab(self._email_tab, "Email")
        self._tab_widget.addTab(self._create_placeholder_tab("Hardware"), "Hardware")
        self._tab_widget.addTab(self._create_placeholder_tab("Tablas"), "Tablas")
        self._tab_widget.addTab(self._save_load_tab, "Guardar / Cargar")
        self._tab_widget.addTab(self._tracking_tab, "Control Tower")
        self._tab_widget.addTab(self._settings_tab, "Configuración")
        self._tab_widget.addTab(self._debug_tab, "Debug")

        self.setCentralWidget(self._tab_widget)

    def _install_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("Archivo")
        new_action = QAction("Nuevo caso", self)
        new_action.triggered.connect(self._new_case)
        file_menu.addAction(new_action)

        save_action = QAction("Guardar autosave", self)
        save_action.triggered.connect(self._manual_autosave)
        file_menu.addAction(save_action)

        export_action = QAction("Exportar PDF…", self)
        export_action.triggered.connect(self._export_pdf)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menu_bar.addMenu("Herramientas")
        refresh_tracking = QAction("Actualizar Tracking", self)
        refresh_tracking.triggered.connect(self._tracking_tab.refresh)
        tools_menu.addAction(refresh_tracking)

        chat_action = QAction("Abrir chat IA", self)
        chat_action.triggered.connect(self._open_chat_window)
        tools_menu.addAction(chat_action)

        help_menu = menu_bar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _configure_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        status_bar.showMessage("Listo")

    def _create_placeholder_tab(self, title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(f"Contenido pendiente para {title}")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        notes = QTextEdit()
        notes.setPlaceholderText("Notas rápidas…")
        layout.addWidget(notes)
        return widget

    # ------------------------------------------------------------------ actions
    def _new_case(self) -> None:
        self._set_case(CaseData())
        self.statusBar().showMessage("Nuevo caso creado", 3000)

    def _manual_autosave(self) -> None:
        case = self._case_tab.current_case()
        try:
            save_autosave(case)
        except Exception as exc:  # pragma: no cover - defensive path
            QMessageBox.warning(self, "Autosave", f"No se pudo guardar: {exc}")
            LOGGER.error("Manual autosave failed: %s", exc)
            return
        self._on_autosave_completed(case)

    def _export_pdf(self) -> None:
        case = self._case_tab.current_case()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar caso a PDF",
            str(get_database_root()),
            "PDF (*.pdf)",
        )
        if not path:
            return
        output_path = Path(path)
        attachments = list(iter_attachments(case))
        try:
            generate_case_pdf(case, output_path=output_path, attachments=attachments)
        except Exception as exc:  # pragma: no cover - defensive path
            LOGGER.error("Failed to export PDF: %s", exc)
            QMessageBox.warning(self, "PDF", f"No se pudo generar el PDF: {exc}")
            return
        QMessageBox.information(self, "PDF", f"PDF guardado en {output_path}")

    def _open_chat_window(self) -> None:
        if self._chat_window is None:
            self._chat_window = ChatWindow(self._ai_client, self._case_tab.current_case)
        self._chat_window.show()
        self._chat_window.raise_()
        self._chat_window.activateWindow()

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "Acerca de",
            "Kiroshi Desktop Experimental\nConstruido con PySide6",
        )

    def _set_case(self, case: CaseData) -> None:
        self._case_tab.set_case(case)
        self.statusBar().showMessage("Caso activo actualizado", 3000)

    def _on_autosave_changed(self, enabled: bool) -> None:
        self._case_tab.set_autosave_enabled(enabled)
        if enabled:
            self.statusBar().showMessage("Autosave activado", 2000)
        else:
            self.statusBar().showMessage("Autosave desactivado", 2000)
        self._config["autosave_enabled"] = enabled
        self._persist_config()

    def _on_autosave_db_changed(self, enabled: bool) -> None:
        self._autosave_to_db_enabled = enabled
        self._config["autosave_to_db"] = enabled
        self._persist_config()
        if enabled:
            try:
                save_case_to_db(self._case_tab.current_case())
            except Exception as exc:  # pragma: no cover - defensive path
                LOGGER.error("Initial DB autosave failed: %s", exc)
                QMessageBox.warning(
                    self,
                    "Autosave",
                    f"No se pudo sincronizar con la base de datos local: {exc}",
                )

    def _on_autosave_completed(self, case: CaseData) -> None:
        timestamp = utc_now_iso()
        self.statusBar().showMessage(f"Autosave completado {timestamp}", 5000)
        if not self._autosave_to_db_enabled:
            return
        try:
            destination = save_case_to_db(case)
        except Exception as exc:  # pragma: no cover - defensive path
            LOGGER.error("Failed to persist case to DB: %s", exc)
            QMessageBox.warning(
                self,
                "Autosave",
                f"Autosave guardado pero no se pudo actualizar la base de datos: {exc}",
            )
            return
        self._save_load_tab.refresh_recent_cases()
        self.statusBar().showMessage(
            f"Autosave actualizado y sincronizado ({Path(destination).name})",
            5000,
        )

    def _on_track_case(self, case: CaseData, enabled: bool) -> None:
        if enabled:
            if not case.case_id:
                QMessageBox.information(
                    self,
                    "Tracking",
                    "Asigna un Case ID antes de activar el tracking.",
                )
                self._case_tab.set_tracking_active(False)
                return
            try:
                start_tracking(case)
            except Exception as exc:  # pragma: no cover - defensive path
                LOGGER.error("Failed to start tracking: %s", exc)
                QMessageBox.warning(self, "Tracking", f"No se pudo iniciar el tracking: {exc}")
                self._case_tab.set_tracking_active(False)
                return
            self._tracking_tab.refresh()
            self.statusBar().showMessage("Caso añadido a tracking", 4000)
        else:
            try:
                stopped = stop_tracking(case.case_id)
            except Exception as exc:  # pragma: no cover - defensive path
                LOGGER.error("Failed to stop tracking: %s", exc)
                QMessageBox.warning(self, "Tracking", f"No se pudo detener el tracking: {exc}")
                self._case_tab.set_tracking_active(True)
                return
            if stopped:
                self._tracking_tab.refresh()
                self.statusBar().showMessage("Tracking desactivado", 3000)
            else:
                self.statusBar().showMessage("No se encontró registro de tracking", 3000)

    def _apply_ai_settings(self, settings: object) -> None:
        if not isinstance(settings, dict):
            return
        mode = str(settings.get("mode", self._ai_client.mode))
        self._ai_client.mode = mode
        self._ai_client.model = str(settings.get("model", self._ai_client.model))
        api_key = settings.get("api_key") or None
        self._ai_client.api_key = str(api_key) if api_key else None
        base_url = settings.get("base_url") or None
        self._ai_client.base_url = str(base_url) if base_url else None
        timeout = settings.get("timeout")
        if isinstance(timeout, int):
            self._ai_client.timeout = timeout

    def _on_ai_settings_changed(self, settings: dict[str, object]) -> None:
        self._config["ai"] = settings
        self._apply_ai_settings(settings)
        self._persist_config()

    def _persist_config(self) -> None:
        try:
            save_global_config(self._config)
        except Exception as exc:  # pragma: no cover - defensive path
            LOGGER.error("Failed to persist config: %s", exc)
