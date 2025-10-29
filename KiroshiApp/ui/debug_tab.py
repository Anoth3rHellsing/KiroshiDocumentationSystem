"""Debug tab with gated diagnostics information."""
from __future__ import annotations

import logging
import platform
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.utils import get_database_root

LOGGER = logging.getLogger(__name__)


class DebugTab(QWidget):
    """Expose debug information after a lightweight authentication check."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logged_in = False
        self._username = QLineEdit()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.Password)
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setPlaceholderText("Introduce credenciales para ver los logs")
        self._system_info = QTextEdit()
        self._system_info.setReadOnly(True)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form_layout = QFormLayout()
        form_layout.addRow(QLabel("Usuario"), self._username)
        form_layout.addRow(QLabel("Contraseña"), self._password)

        login_button = QPushButton("Login")
        login_button.clicked.connect(self._attempt_login)

        top_row = QHBoxLayout()
        top_row.addLayout(form_layout)
        top_row.addWidget(login_button)
        layout.addLayout(top_row)

        layout.addWidget(QLabel("Logs recientes"))
        layout.addWidget(self._log_view, 3)
        layout.addWidget(QLabel("Información del sistema"))
        layout.addWidget(self._system_info, 2)

    def _attempt_login(self) -> None:
        if self._logged_in:
            return
        username = self._username.text().strip()
        password = self._password.text().strip()
        if username.lower() == "debug" and password == "kiroshi":
            self._logged_in = True
            self._username.setEnabled(False)
            self._password.setEnabled(False)
            self._load_debug_data()
            QMessageBox.information(self, "Debug", "Acceso concedido")
        else:
            QMessageBox.warning(self, "Debug", "Credenciales inválidas")

    def _load_debug_data(self) -> None:
        log_path = get_database_root() / "kiroshi.log"
        if log_path.exists():
            try:
                lines = log_path.read_text(encoding="utf-8").splitlines()
                tail = "\n".join(lines[-200:])
                self._log_view.setPlainText(tail)
            except Exception as exc:  # pragma: no cover - defensive path
                LOGGER.error("Failed to read log file: %s", exc)
                self._log_view.setPlainText(f"No se pudieron leer los logs: {exc}")
        else:
            self._log_view.setPlainText("No se encontraron logs")

        system_lines = [
            f"Plataforma: {platform.platform()}",
            f"Hostname: {platform.node()}",
            f"Python: {platform.python_version()}",
        ]
        self._system_info.setPlainText("\n".join(system_lines))
