"""Simple AI chat assistant dialog."""
from __future__ import annotations

import logging
from typing import Callable, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

LOGGER = logging.getLogger(__name__)


class ChatWindow(QDialog):
    """Interactive dialog that proxies conversation to :class:`AIClient`."""

    def __init__(
        self,
        ai_client: AIClient,
        case_getter: Callable[[], CaseData],
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self._ai_client = ai_client
        self._case_getter = case_getter
        self._history: List[Tuple[str, str]] = []

        self.setWindowTitle("Asistente IA")
        self.resize(640, 480)

        self._history_view = QTextEdit()
        self._history_view.setReadOnly(True)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Escribe tu mensaje…")

        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._history_view)
        layout.addWidget(self._input)
        layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        send_button = QPushButton("Enviar")
        send_button.clicked.connect(self._on_send_clicked)
        button_row.addWidget(send_button)

        clear_button = QPushButton("Limpiar")
        clear_button.clicked.connect(self._clear_history)
        button_row.addWidget(clear_button)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.close)
        button_row.addWidget(close_button)

        button_row.addStretch()
        layout.addLayout(button_row)

    def _on_send_clicked(self) -> None:
        message = self._input.toPlainText().strip()
        if not message:
            return
        self._append_history("Usuario", message)
        self._input.clear()
        self._status_label.setText("Generando respuesta…")
        QApplication.processEvents()

        try:
            response = self._invoke_ai(message)
        except Exception as exc:  # pragma: no cover - network failures
            LOGGER.error("Chat completion failed: %s", exc)
            QMessageBox.warning(self, "IA", f"No se pudo obtener respuesta: {exc}")
            self._status_label.setText("Error")
            return

        self._append_history("Asistente", response.strip())
        self._status_label.setText("Respuesta recibida")

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
        formatted = "\n".join(f"{s}: {t}" for s, t in self._history)
        self._history_view.setPlainText(formatted)
        self._history_view.moveCursor(self._history_view.textCursor().End)

    def _clear_history(self) -> None:
        self._history.clear()
        self._history_view.clear()
        self._status_label.clear()


try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - guard for type checkers
    QApplication = object  # type: ignore
