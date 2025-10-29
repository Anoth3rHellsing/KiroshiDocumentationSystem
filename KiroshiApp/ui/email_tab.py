"""Email tab providing templates and AI assisted drafting."""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QWidget,
)

from ..core.ai_client import AIClient
from ..core.model import CaseData
from .background import run_in_threadpool

LOGGER = logging.getLogger(__name__)


class EmailTab(QWidget):
    """Provide manual templates and AI powered body generation."""

    DEFAULT_TEMPLATES: dict[str, str] = {
        "Seguimiento": (
            "Hola {caller},\n\n"
            "Gracias por ponerte en contacto con 3Shape Support. "
            "Confirmamos que el caso {case_id} permanece resuelto."
            "\n\nResumen: {summary}\nPróximos pasos: {next_steps}\n\nSaludos,\nEquipo Kiroshi"
        ),
        "Resolución": (
            "Estimado/a {caller},\n\n"
            "El incidente {case_id} ha sido solucionado. "
            "Solución aplicada: {solution}.\n\n"
            "Notas adicionales: {next_steps}\n\nUn saludo,\nEquipo Kiroshi"
        ),
        "Escalación": (
            "Hola {caller},\n\nTu caso {case_id} se encuentra en escalación. "
            "Estamos trabajando con {company} para resolverlo."
            "\nEstado actual: {summary}\n\nAtentamente,\nEquipo Kiroshi"
        ),
    }

    def __init__(
        self,
        case_getter: Callable[[], CaseData],
        ai_client: AIClient,
        parent: QWidget | None = None,
        *,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self._case_getter = case_getter
        self._ai_client = ai_client
        self._thread_pool = thread_pool or QThreadPool.globalInstance()

        self._template_selector = QComboBox()
        self._preview = QTextEdit()
        self._preview.setAcceptRichText(False)
        self._preview.setPlaceholderText("Previsualización de email…")
        self._status_label = QLabel()
        self._generate_button: QPushButton | None = None

        self._build_ui()
        self._refresh_preview()

    def _build_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(8)

        layout.addWidget(QLabel("Plantilla"), 0, 0)
        self._template_selector.addItems(self.DEFAULT_TEMPLATES.keys())
        self._template_selector.currentIndexChanged.connect(self._refresh_preview)
        layout.addWidget(self._template_selector, 0, 1)

        self._generate_button = QPushButton("Generar con IA")
        self._generate_button.clicked.connect(self._on_generate_clicked)
        layout.addWidget(self._generate_button, 0, 2)

        copy_button = QPushButton("Copiar al portapapeles")
        copy_button.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(copy_button, 0, 3)

        layout.addWidget(self._preview, 1, 0, 1, 4)
        self._status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._status_label, 2, 0, 1, 4)

    def _refresh_preview(self) -> None:
        case = self._case_getter()
        template_name = self._template_selector.currentText()
        template = self.DEFAULT_TEMPLATES.get(template_name, "{summary}")
        text = template.format(
            caller=case.caller_name or case.contact_name or "cliente",
            case_id=case.case_id or "N/D",
            summary=case.brief_description or case.description,
            solution=case.solution or "",
            next_steps=case.additional_info or "",
            company=case.company_name or "el cliente",
        )
        self._preview.setPlainText(text.strip())
        self._status_label.setText("")

    def _on_generate_clicked(self) -> None:
        case = self._case_getter()
        if self._generate_button:
            self._generate_button.setEnabled(False)
        self._status_label.setText("Generando con IA…")

        def _on_success(result: str) -> None:
            self._preview.setPlainText(result.strip())
            self._status_label.setText("Generado con IA")
            if self._generate_button:
                self._generate_button.setEnabled(True)

        def _on_error(exc: Exception) -> None:
            LOGGER.error("AI email generation failed: %s", exc)
            QMessageBox.warning(self, "IA", f"No se pudo generar el correo: {exc}")
            self._status_label.setText("Error al generar IA")
            if self._generate_button:
                self._generate_button.setEnabled(True)

        run_in_threadpool(
            self._ai_client.generate_email_body,
            args=(case,),
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    def _copy_to_clipboard(self) -> None:
        text = self._preview.toPlainText()
        QApplication.clipboard().setText(text)
        self._status_label.setText("Copiado al portapapeles")
