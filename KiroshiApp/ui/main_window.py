"""Main window wiring together all desktop tabs."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
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
from ..core.model import CaseData
from ..core.storage import save_autosave
from ..core.utils import utc_now_iso
from .case_tab import CaseTab
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
        self._ai_client = ai_client or AIClient()
        self._case_tab = CaseTab(case)
        self._email_tab = EmailTab(self._case_tab.current_case, self._ai_client)
        self._tracking_tab = TrackingTab()
        self._settings_tab = SettingsTab(self._on_autosave_changed)
        self._debug_tab = DebugTab()
        self._save_load_tab = SaveLoadTab(
            self._case_tab.current_case,
            self._set_case,
            autosave_toggle=self._case_tab.set_autosave_enabled,
        )

        self._tab_widget = QTabWidget()
        self._build_ui()
        self._connect_autosave_status()

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
        export_action.triggered.connect(self._export_pdf_placeholder)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools_menu = menu_bar.addMenu("Herramientas")
        refresh_tracking = QAction("Actualizar Tracking", self)
        refresh_tracking.triggered.connect(self._tracking_tab.refresh)
        tools_menu.addAction(refresh_tracking)

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

    def _connect_autosave_status(self) -> None:
        def _update_status(_: CaseData) -> None:
            timestamp = utc_now_iso()
            self.statusBar().showMessage(f"Autosave completado {timestamp}", 5000)

        self._case_tab.on_manual_autosave(_update_status)

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
        self.statusBar().showMessage("Autosave guardado manualmente", 4000)

    def _export_pdf_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "PDF",
            "Generación de PDF pendiente de implementación en la fase siguiente.",
        )

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
