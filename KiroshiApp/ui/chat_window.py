"""Simple AI chat assistant dialog."""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..core.ai_client import AIClient
from ..core.model import CaseData
from .background import run_in_threadpool

LOGGER = logging.getLogger(__name__)


class ChatWindow(QDialog):
    """Interactive dialog that proxies conversation to :class:`AIClient`."""

    def __init__(
        self,
        ai_client: AIClient,
        case_getter: Callable[[], CaseData],
        parent: QDialog | None = None,
        *,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self._ai_client = ai_client
        self._case_getter = case_getter
        self._history: list[tuple[str, str]] = []
        self._thread_pool = thread_pool or QThreadPool.globalInstance()

        self.setWindowTitle("Asistente IA")
        self.resize(640, 480)

        self._history_view = QTextEdit()
        self._history_view.setReadOnly(True)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Escribe tu mensaje…")

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._send_button: QPushButton | None = None
        self._mode_selector: QComboBox | None = None
        self._reassurance_toggle: QCheckBox | None = None
        self._reassure_button: QPushButton | None = None
        self._results_panel = QTextEdit()
        self._results_panel.setReadOnly(True)

        self._build_ui()
        self._hydrate_history()
        self._sync_mode_selector()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._history_view)
        layout.addWidget(self._input)
        layout.addWidget(self._status_label)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_label = QLabel("Modo:")
        mode_row.addWidget(mode_label)
        self._mode_selector = QComboBox()
        self._mode_selector.addItems(["Comfort", "Sarcasm"])
        self._mode_selector.currentTextChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_selector)

        self._reassurance_toggle = QCheckBox("Agregar reassurance en la próxima respuesta")
        mode_row.addWidget(self._reassurance_toggle)

        self._reassure_button = QPushButton("Reassurance ahora")
        self._reassure_button.clicked.connect(self._on_reassure_clicked)
        mode_row.addWidget(self._reassure_button)

        mode_row.addStretch()
        layout.addLayout(mode_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)
        verify_button = QPushButton("Verify")
        verify_button.clicked.connect(self._on_verify_clicked)
        actions_row.addWidget(verify_button)

        educate_button = QPushButton("Answer with Educate")
        educate_button.clicked.connect(self._on_educate_clicked)
        actions_row.addWidget(educate_button)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        button_row = QHBoxLayout()
        self._send_button = QPushButton("Enviar")
        self._send_button.clicked.connect(self._on_send_clicked)
        button_row.addWidget(self._send_button)

        clear_button = QPushButton("Limpiar")
        clear_button.clicked.connect(self._clear_history)
        button_row.addWidget(clear_button)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.close)
        button_row.addWidget(close_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        layout.addWidget(QLabel("Panel de acciones"))
        layout.addWidget(self._results_panel)

    def _hydrate_history(self) -> None:
        """Load any persisted exchanges into the view."""

        stored = self._ai_client.get_conversation_history()
        if not stored:
            return

        for entry in stored:
            role = entry.get("role", "")
            content = str(entry.get("content", "")).strip()
            if not content:
                continue
            speaker = "Usuario" if role == "user" else "Asistente"
            self._history.append((speaker, content))

        self._refresh_history_view()

    def _sync_mode_selector(self) -> None:
        if not self._mode_selector:
            return
        current_mode = self._ai_client.get_personality_mode()
        label = "Sarcasm" if current_mode == "sarcasm" else "Comfort"
        index = self._mode_selector.findText(label)
        if index >= 0:
            self._mode_selector.setCurrentIndex(index)

    def _on_send_clicked(self) -> None:
        message = self._input.toPlainText().strip()
        if not message:
            return
        if self._reassurance_toggle and self._reassurance_toggle.isChecked():
            message += (
                "\n\nNota: el usuario solicita reassurance adicional con un tono calmado y positivo."
            )
            self._reassurance_toggle.setChecked(False)
        self._append_history("Usuario", message)
        self._input.clear()
        if self._send_button:
            self._send_button.setEnabled(False)
        self._status_label.setText("Generando respuesta…")

        def _on_success(response: str) -> None:
            self._append_history("Asistente", response.strip())
            self._status_label.setText("Respuesta recibida")
            if self._send_button:
                self._send_button.setEnabled(True)

        def _on_error(exc: Exception) -> None:
            LOGGER.error("Chat completion failed: %s", exc)
            QMessageBox.warning(self, "IA", f"No se pudo obtener respuesta: {exc}")
            self._status_label.setText("Error")
            if self._send_button:
                self._send_button.setEnabled(True)

        run_in_threadpool(
            self._invoke_ai,
            args=(message,),
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    def _invoke_ai(self, message: str) -> str:
        case = self._case_getter()
        summary = case.brief_description or case.description or "Sin resumen"
        solution = case.solution or ""
        conversation = "\n".join(
            f"{speaker}: {text}" for speaker, text in self._history[-6:]
        )
        prompt = (
            "Eres un asistente que ayuda al ingeniero con preguntas sobre el caso actual.\n"
            f"Caso: {case.case_id}\nEmpresa: {case.company_name}\n"
            f"Resumen: {summary}\nSolución: {solution}\n\n"
            f"Conversación previa:\n{conversation}\n\nUsuario: {message}\nAsistente:"
        )
        return self._ai_client.invoke_completion(prompt)

    def _append_history(self, speaker: str, text: str) -> None:
        self._history.append((speaker, text))
        self._refresh_history_view()

    def _refresh_history_view(self) -> None:
        formatted = "\n".join(f"{s}: {t}" for s, t in self._history)
        self._history_view.setPlainText(formatted)
        self._history_view.moveCursor(self._history_view.textCursor().End)

    def _clear_history(self) -> None:
        self._history.clear()
        self._history_view.clear()
        self._status_label.clear()
        self._results_panel.clear()
        self._ai_client.reset_history()

    def _on_mode_changed(self, text: str) -> None:
        try:
            self._ai_client.set_personality_mode(text)
        except ValueError:
            LOGGER.warning("Modo de personalidad no válido: %s", text)

    def _on_verify_clicked(self) -> None:
        self._status_label.setText("Verificando caso…")

        def _task() -> list[dict[str, str]]:
            return self._ai_client.verify_case_data(self._case_getter())

        def _on_success(result: list[dict[str, str]]) -> None:
            if not result:
                summary = "✅ Todos los campos están completos."
            else:
                lines = []
                for entry in result:
                    severity = entry.get("severity", "info")
                    label = entry.get("label", entry.get("field", ""))
                    prefix = "⚠️" if severity == "critical" else "•"
                    lines.append(f"{prefix} {label} está vacío")
                summary = "\n".join(lines)
            self._results_panel.setPlainText(summary)
            self._status_label.setText("Verificación completada")

        def _on_error(exc: Exception) -> None:
            LOGGER.error("Verify failed: %s", exc)
            self._status_label.setText("Error en Verify")
            QMessageBox.warning(self, "Verify", f"No se pudo verificar el caso: {exc}")

        run_in_threadpool(
            _task,
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    def _on_educate_clicked(self) -> None:
        self._append_history("Usuario", "Solicitar respuesta tipo Educate")
        self._status_label.setText("Generando respuesta educativa…")

        def _task() -> str:
            case = self._case_getter()
            summary = case.brief_description or case.description or "Sin resumen"
            return self._ai_client.invoke_completion(
                (
                    "Actúa como mentor técnico y prepara una respuesta estilo Educate "
                    "para el ingeniero que trabaja en este caso. Explica brevemente el contexto, "
                    "qué revisar y próximos pasos sugeridos."
                    f"\n\nCaso: {case.case_id}\nEmpresa: {case.company_name}\n"
                    f"Resumen: {summary}\nNotas adicionales: {case.additional_info}\n"
                )
            )

        def _on_success(response: str) -> None:
            clean = response.strip()
            self._append_history("Asistente", clean)
            self._results_panel.setPlainText(clean)
            self._status_label.setText("Educate listo")

        def _on_error(exc: Exception) -> None:
            LOGGER.error("Educate failed: %s", exc)
            self._status_label.setText("Error en Educate")
            QMessageBox.warning(self, "Educate", f"No se pudo obtener respuesta: {exc}")

        run_in_threadpool(
            _task,
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    def _on_reassure_clicked(self) -> None:
        self._append_history("Usuario", "Solicitar reassurance inmediata")
        self._status_label.setText("Generando reassurance…")

        def _task() -> str:
            return self._ai_client.invoke_completion(
                "El ingeniero está abrumado y necesita reassurance breve pero útil para continuar con el caso."
            )

        def _on_success(response: str) -> None:
            clean = response.strip()
            self._append_history("Asistente", clean)
            self._results_panel.setPlainText(clean)
            self._status_label.setText("Reassurance enviado")

        def _on_error(exc: Exception) -> None:
            LOGGER.error("Reassurance failed: %s", exc)
            self._status_label.setText("Error en reassurance")
            QMessageBox.warning(self, "Reassurance", f"No se pudo obtener respuesta: {exc}")

        run_in_threadpool(
            _task,
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )
