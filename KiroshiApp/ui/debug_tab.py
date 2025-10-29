"""Debug tab with protected access and diagnostic utilities."""
from __future__ import annotations

import json
import platform
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.logs import LogSnapshot, load_recent_logs, resolve_log_file_path
from KiroshiApp.core.storage import get_database_root


class DebugTab(QWidget):
    """Debugging utilities protected behind a simple admin login."""

    def __init__(self) -> None:
        super().__init__()
        self._authenticated = False
        self._current_log_snapshot: LogSnapshot | None = None

        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(5_000)
        self._auto_refresh_timer.timeout.connect(self._refresh_logs)

        self._stack = QStackedLayout(self)
        self._login_widget = self._build_login_widget()
        self._debug_widget = self._build_debug_widget()
        self._stack.addWidget(self._login_widget)
        self._stack.addWidget(self._debug_widget)
        self._stack.setCurrentWidget(self._login_widget)

    # ------------------------------------------------------------------
    # Login flow
    def _build_login_widget(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.addStretch()

        banner = QLabel("Acceso restringido")
        banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(banner)

        message = QLabel(
            "Esta sección contiene herramientas internas. "
            "Inicia sesión con las credenciales de administrador para continuar."
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(message)

        self._username = QLineEdit()
        self._username.setPlaceholderText("Usuario")
        self._username.setMaxLength(64)
        self._username.setClearButtonEnabled(True)
        layout.addWidget(self._username)

        self._password = QLineEdit()
        self._password.setPlaceholderText("Contraseña")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setClearButtonEnabled(True)
        layout.addWidget(self._password)

        self._login_feedback = QLabel()
        self._login_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._login_feedback.setStyleSheet("color: #c62828;")
        layout.addWidget(self._login_feedback)

        login_button = QPushButton("Acceder")
        login_button.clicked.connect(self._handle_login_attempt)
        layout.addWidget(login_button)

        self._password.returnPressed.connect(self._handle_login_attempt)
        layout.addStretch()
        return container

    def _handle_login_attempt(self) -> None:
        username = self._username.text().strip()
        password = self._password.text().strip()
        if username == "admin" and password == "admin":
            self._login_feedback.clear()
            self._set_authenticated(True)
            return

        self._login_feedback.setText("Credenciales no válidas. Inténtalo de nuevo.")
        self._password.setFocus()
        self._password.selectAll()

    def _set_authenticated(self, value: bool) -> None:
        if self._authenticated == value:
            return

        self._authenticated = value
        if value:
            self._stack.setCurrentWidget(self._debug_widget)
            self._username.clear()
            self._password.clear()
            self._start_auto_refresh()
            self._refresh_logs()
            self._refresh_configuration_snapshot()
        else:
            self._stack.setCurrentWidget(self._login_widget)
            self._auto_refresh_timer.stop()

    # ------------------------------------------------------------------
    # Debug widgets
    def _build_debug_widget(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        intro = QLabel(
            "Herramientas de diagnóstico para validar el estado de la aplicación "
            "sin exponer información sensible a usuarios no autorizados."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(self._build_log_group())
        layout.addWidget(self._build_connectivity_group())
        layout.addWidget(self._build_configuration_group())
        layout.addStretch()
        return container

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Registros de la aplicación")
        group_layout = QVBoxLayout(group)

        self._log_path_label = QLabel("Archivo de log: …")
        self._log_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        group_layout.addWidget(self._log_path_label)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setPlaceholderText("No hay información disponible todavía.")
        self._log_view.setMinimumHeight(220)
        group_layout.addWidget(self._log_view)

        controls = QHBoxLayout()
        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self._refresh_logs)
        controls.addWidget(refresh_button)

        self._auto_refresh_checkbox = QCheckBox("Autoactualizar cada 5 s")
        self._auto_refresh_checkbox.setChecked(True)
        self._auto_refresh_checkbox.toggled.connect(self._toggle_auto_refresh)
        controls.addWidget(self._auto_refresh_checkbox)

        copy_button = QPushButton("Copiar todo")
        copy_button.clicked.connect(self._copy_logs_to_clipboard)
        controls.addWidget(copy_button)

        download_button = QPushButton("Descargar…")
        download_button.clicked.connect(self._download_logs)
        controls.addWidget(download_button)

        controls.addStretch()
        group_layout.addLayout(controls)

        self._log_status_label = QLabel()
        self._log_status_label.setStyleSheet("color: #2e7d32;")
        group_layout.addWidget(self._log_status_label)
        return group

    def _build_connectivity_group(self) -> QGroupBox:
        group = QGroupBox("Pruebas de conectividad")
        layout = QVBoxLayout(group)

        hint = QLabel(
            "Comprueba rápidamente si el equipo puede comunicarse con un destino determinado."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addWidget(QLabel("Destino:"))
        self._connectivity_target = QLineEdit("https://example.com")
        self._connectivity_target.setClearButtonEnabled(True)
        row.addWidget(self._connectivity_target)
        layout.addLayout(row)

        run_button = QPushButton("Probar conexión")
        run_button.clicked.connect(self._run_connectivity_test)
        layout.addWidget(run_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self._connectivity_status = QLabel("Pendiente de ejecución.")
        self._connectivity_status.setWordWrap(True)
        layout.addWidget(self._connectivity_status)
        return group

    def _build_configuration_group(self) -> QGroupBox:
        group = QGroupBox("Inspector de configuración")
        layout = QVBoxLayout(group)

        refresh_button = QPushButton("Actualizar instantánea")
        refresh_button.clicked.connect(self._refresh_configuration_snapshot)
        layout.addWidget(refresh_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self._config_view = QPlainTextEdit()
        self._config_view.setReadOnly(True)
        self._config_view.setPlaceholderText("Pulsa en \"Actualizar instantánea\" para recopilar datos.")
        self._config_view.setMinimumHeight(180)
        layout.addWidget(self._config_view)

        self._config_status = QLabel()
        self._config_status.setWordWrap(True)
        layout.addWidget(self._config_status)
        return group

    # ------------------------------------------------------------------
    # Log helpers
    def _toggle_auto_refresh(self, checked: bool) -> None:
        if checked:
            self._start_auto_refresh()
        else:
            self._auto_refresh_timer.stop()

    def _start_auto_refresh(self) -> None:
        if not self._auto_refresh_checkbox.isChecked():
            return
        if not self._auto_refresh_timer.isActive():
            self._auto_refresh_timer.start()

    def _refresh_logs(self) -> None:
        snapshot = load_recent_logs()
        self._current_log_snapshot = snapshot
        self._log_path_label.setText(f"Archivo de log: {snapshot.path}")

        if snapshot.ok:
            self._log_view.setPlainText(snapshot.content)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self._log_status_label.setStyleSheet("color: #2e7d32;")
            self._log_status_label.setText(f"Actualizado correctamente a las {timestamp}.")
        else:
            self._log_view.clear()
            self._log_status_label.setStyleSheet("color: #c62828;")
            self._log_status_label.setText(snapshot.error or "No se pudo leer el archivo de log.")

    def _copy_logs_to_clipboard(self) -> None:
        if not self._current_log_snapshot or not self._current_log_snapshot.ok:
            self._log_status_label.setStyleSheet("color: #c62828;")
            self._log_status_label.setText("No hay contenido para copiar.")
            return

        QApplication.clipboard().setText(self._current_log_snapshot.content)
        self._log_status_label.setStyleSheet("color: #2e7d32;")
        self._log_status_label.setText("Contenido copiado al portapapeles.")

    def _download_logs(self) -> None:
        if not self._current_log_snapshot or not self._current_log_snapshot.ok:
            self._log_status_label.setStyleSheet("color: #c62828;")
            self._log_status_label.setText("No hay contenido para descargar.")
            return

        default_path = self._suggest_log_destination()
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar log",
            str(default_path),
            "Archivos de texto (*.log *.txt);;Todos los archivos (*.*)",
        )
        if not filename:
            return

        try:
            Path(filename).write_text(self._current_log_snapshot.content, encoding="utf-8")
        except OSError as exc:
            self._log_status_label.setStyleSheet("color: #c62828;")
            self._log_status_label.setText(f"No se pudo guardar el archivo: {exc}")
            return

        self._log_status_label.setStyleSheet("color: #2e7d32;")
        self._log_status_label.setText(f"Log guardado en {filename}.")

    def _suggest_log_destination(self) -> Path:
        log_path = (
            self._current_log_snapshot.path
            if self._current_log_snapshot
            else resolve_log_file_path()
        )
        base_name = f"{log_path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        return log_path.with_name(base_name)

    # ------------------------------------------------------------------
    # Connectivity helpers
    def _run_connectivity_test(self) -> None:
        target = self._connectivity_target.text().strip()
        if not target:
            self._connectivity_status.setStyleSheet("color: #c62828;")
            self._connectivity_status.setText("Introduce una URL o host de destino.")
            return

        parsed = urlparse(target if "://" in target else f"https://{target}")
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme in {"https", "wss"} else 80)
        if not host:
            self._connectivity_status.setStyleSheet("color: #c62828;")
            self._connectivity_status.setText("No se pudo interpretar el destino indicado.")
            return

        self._connectivity_status.setStyleSheet("color: #546e7a;")
        self._connectivity_status.setText(f"Comprobando conectividad con {host}:{port}…")

        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=5):
                pass
        except OSError as exc:
            self._connectivity_status.setStyleSheet("color: #c62828;")
            self._connectivity_status.setText(f"Error al conectar con {host}:{port}: {exc}")
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._connectivity_status.setStyleSheet("color: #2e7d32;")
        self._connectivity_status.setText(
            f"Conexión exitosa con {host}:{port} en {elapsed_ms:.0f} ms."
        )

    # ------------------------------------------------------------------
    # Configuration helpers
    def _refresh_configuration_snapshot(self) -> None:
        snapshot = self._collect_configuration_snapshot()
        self._config_view.setPlainText(snapshot)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._config_status.setText(f"Instantánea generada a las {timestamp}.")

    def _collect_configuration_snapshot(self) -> str:
        settings = self._load_persisted_settings()
        log_path = (
            self._current_log_snapshot.path
            if self._current_log_snapshot
            else resolve_log_file_path()
        )
        summary = {
            "sistema": platform.platform(),
            "python": sys.version.split()[0],
            "directorio_trabajo": str(Path.cwd()),
            "archivo_log": str(log_path),
            "configuracion_guardada": settings,
        }
        return json.dumps(summary, ensure_ascii=False, indent=2)

    def _load_persisted_settings(self) -> dict[str, object]:
        try:
            root = get_database_root(None)
        except Exception:  # pragma: no cover - defensive fallback
            return {}
        config_path = root / "settings.json"
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
