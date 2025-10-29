"""Email prompt generator tab for the desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.ai_client import AIClient
from ..core.model import CaseData, RemoteSessionEntry
from .background import run_in_threadpool


@dataclass(frozen=True)
class TemplateDefinition:
    """Metadata describing a preconfigured email template."""

    value: str
    label: str
    description: str
    group: str
    icon: str = ""
    second_line_only: bool = False
    prompt_builder: Callable[[CaseData, str, str], str] | None = None
    use_generate_email: bool = False


def _format_remote_sessions(case: CaseData) -> str:
    """Return a bullet list summary of remote troubleshooting steps."""

    lines: List[str] = []
    for entry in case.remote_sessions:
        if isinstance(entry, RemoteSessionEntry):
            note = (entry.notes or "").strip()
            title = (entry.title or "").strip()
            content = note or title
            if content:
                lines.append(f"- {content}")
    if not lines:
        for raw_line in (case.remote_steps or "").splitlines():
            text = raw_line.strip()
            if text:
                lines.append(f"- {text}")
    if case.solution:
        lines.append(f"Solución propuesta: {case.solution}")
    if not lines:
        lines.append("- No hay pasos registrados")
    return "\n".join(lines)


def _default_email_prompt(case: CaseData, tone: str, audience: str) -> str:
    """Return the default prompt used by :meth:`AIClient.generate_email_body`."""

    summary = _format_remote_sessions(case)
    description = case.brief_description or case.description or "Sin resumen disponible"
    additional = case.additional_info or "Sin notas adicionales"
    return (
        "Compose a professional email update for the following support case.\n"
        f"Case ID: {case.case_id or 'N/A'}\n"
        f"Company: {case.company_name or 'N/A'}\n"
        f"Issue: {description}\n"
        f"Troubleshooting summary:\n{summary}\n"
        f"Additional notes: {additional}\n"
        f"Tone: {tone}\n"
        f"Audience: {audience}"
    )


def _recap_prompt(case: CaseData, tone: str, audience: str) -> str:
    intro = (
        "You are a support specialist preparing a recap email that motivates the customer to"
        " stay engaged with the case."
    )
    survey = case.survey_link or ""
    survey_line = (
        f"Invite the customer to complete the satisfaction survey available at {survey}.\n"
        if survey
        else ""
    )
    return (
        f"{intro}\n"
        f"Write in a {tone} tone for a {audience}.\n"
        "Summarise the situation, highlight the solution, and clearly state next actions.\n"
        f"Case ID: {case.case_id or 'Sin ID'}\n"
        f"Customer: {case.company_name or 'Sin empresa'}\n"
        f"Contact name: {case.contact_name or case.caller_name or 'Sin contacto'}\n"
        f"Summary: {case.brief_description or case.description or 'Sin resumen'}\n"
        f"Key troubleshooting steps:\n{_format_remote_sessions(case)}\n"
        f"Outcome or solution: {case.solution or 'Pendiente'}\n"
        f"Additional context: {case.additional_info or 'Sin información adicional'}\n"
        f"{survey_line}Close with gratitude and offer further assistance."
    )


def _customer_reply_prompt(case: CaseData, tone: str, audience: str) -> str:
    return (
        "You received a follow-up email from the customer for an active support case."
        " Draft a reply that acknowledges their concerns, confirms understanding of the"
        " issue, and lists the next steps you will take."
        f" Use a {tone} tone targeting a {audience}.\n"
        f"Case reference: {case.case_id or 'N/A'}\n"
        f"Company: {case.company_name or 'N/A'}\n"
        f"Problem summary: {case.brief_description or case.description or 'No summary provided'}\n"
        f"Most recent actions:\n{_format_remote_sessions(case)}\n"
        f"Solution in progress: {case.solution or 'Sin solución documentada'}\n"
        "Close the email by inviting the customer to ask further questions and providing"
        " a clear commitment on the next update. Return only the email body."
    )


def _broken_tip_prompt(case: CaseData, tone: str, audience: str) -> str:
    return (
        "Craft an instructional email explaining how to handle a broken scanner tip."
        " Provide safety guidance, shipping or replacement steps, and highlight any"
        " troubleshooting already performed."
        f" Keep the tone {tone} for a {audience}.\n"
        f"Case ID: {case.case_id or 'N/A'}\n"
        f"Clinic: {case.company_name or 'N/A'}\n"
        f"Reported issue: {case.brief_description or case.description or 'No description'}\n"
        f"Steps already tried:\n{_format_remote_sessions(case)}\n"
        f"Current resolution plan: {case.solution or 'Replacement pending'}\n"
        "Clearly list the actions the clinic must perform next and any packaging or"
        " contact instructions. Return only the email body."
    )


def _escalation_prompt(case: CaseData, tone: str, audience: str) -> str:
    return (
        "Prepare an escalation email for a hardware vendor. Summarise the customer impact,"
        " troubleshooting completed, and any logs gathered."
        f" Tone should be {tone} and audience is {audience}.\n"
        f"Case ID: {case.case_id or 'N/A'}\n"
        f"Customer: {case.company_name or 'N/A'}\n"
        f"Escalation contact: {case.esc_name or 'Sin asignar'} ({case.esc_email or 'sin email'})\n"
        f"Technical summary:\n{_format_remote_sessions(case)}\n"
        f"Key findings / root cause: {case.root_cause or 'Pendiente'}\n"
        f"Requested action: {case.third_line_troubleshoot_summary or case.additional_info or 'Asistencia prioritaria'}\n"
        "Structure the email with an opening context, detailed summary, and explicit next steps."
    )


def _tracking_prompt(case: CaseData, tone: str, audience: str) -> str:
    return (
        "Write an email that shares shipping or tracking information with the recipient."
        f" Tone: {tone}. Audience: {audience}.\n"
        f"Case ID: {case.case_id or 'N/A'}\n"
        f"Company: {case.company_name or 'N/A'}\n"
        f"Tracking number: {case.tracking.ticket_number or case.tracking.case_link or 'No tracking info'}\n"
        f"Expected arrival date: {case.tracking.expected_arrival_date or 'Sin fecha confirmada'}\n"
        f"Summary of work performed:\n{_format_remote_sessions(case)}\n"
        "Reassure the customer, state what to do if there are issues, and confirm next follow-up."
    )


def _callback_prompt(case: CaseData, tone: str, audience: str) -> str:
    return (
        "Draft an email confirming a scheduled callback or remote session."
        f" Use a {tone} tone suitable for a {audience}.\n"
        f"Case ID: {case.case_id or 'N/A'}\n"
        f"Customer: {case.company_name or 'N/A'}\n"
        f"Contact: {case.contact_name or case.caller_name or 'Sin contacto'}\n"
        f"Best time provided: {case.best_time or 'No especificado'}\n"
        f"Phone numbers: {case.phone_number or case.direct_ph or 'Sin teléfono'}\n"
        f"Troubleshooting performed:\n{_format_remote_sessions(case)}\n"
        "Clarify what will happen during the callback and how the customer can reschedule."
    )


TEMPLATE_DEFINITIONS: Sequence[TemplateDefinition] = (
    TemplateDefinition(
        value="Recap (Customer)",
        label="Recap (Customer)",
        description="Recap cálido con invitación a encuesta y siguientes pasos claros.",
        group="Customer follow-up",
        icon="💌",
        prompt_builder=_recap_prompt,
        use_generate_email=True,
    ),
    TemplateDefinition(
        value="Customer Reply",
        label="Customer Reply",
        description="Responder con confianza a un correo entrante del cliente.",
        group="Customer follow-up",
        icon="✉️",
        prompt_builder=_customer_reply_prompt,
    ),
    TemplateDefinition(
        value="Broken Tip",
        label="Broken Tip",
        description="Guía para problemas con puntas dañadas y próximos pasos.",
        group="Hardware fixes",
        icon="🧰",
        prompt_builder=_broken_tip_prompt,
    ),
    TemplateDefinition(
        value="FedEx Tracking Email",
        label="FedEx Tracking Email",
        description="Compartir actualizaciones de envío y expectativas con el cliente.",
        group="Internal sync",
        icon="📦",
        second_line_only=True,
        prompt_builder=_tracking_prompt,
    ),
    TemplateDefinition(
        value="Callback Email",
        label="Callback Email",
        description="Confirmar un callback programado con instrucciones claras.",
        group="Internal sync",
        icon="📞",
        second_line_only=True,
        prompt_builder=_callback_prompt,
    ),
    TemplateDefinition(
        value="Dell Escalation Email",
        label="Dell Escalation Email",
        description="Escalar casos urgentes con contexto conciso y acciones esperadas.",
        group="Internal sync",
        icon="🚀",
        second_line_only=True,
        prompt_builder=_escalation_prompt,
    ),
)


TONE_OPTIONS: Sequence[tuple[str, str]] = (
    ("Neutro", "neutral"),
    ("Cálido", "friendly"),
    ("Formal", "formal"),
    ("Empático", "empathetic"),
)


AUDIENCE_OPTIONS: Sequence[tuple[str, str]] = (
    ("Cliente", "customer"),
    ("Reseller", "reseller"),
    ("Interno", "internal"),
)

from KiroshiApp.core.model import CaseData


class EmailTab(QWidget):
    """Interactive email template browser with AI generation helpers."""

    def __init__(
        self,
        case: CaseData,
        ai_client: AIClient,
        parent: QWidget | None = None,
        *,
        thread_pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self._case = case
        self._ai_client = ai_client
        self._thread_pool = thread_pool or QThreadPool.globalInstance()
        self._template_lookup = {t.value: t for t in TEMPLATE_DEFINITIONS}
        self._auto_prompt_text = ""
        self._setting_prompt = False

        self._template_list: QListWidget | None = None
        self._template_description: QLabel | None = None
        self._prompt_editor: QPlainTextEdit | None = None
        self._tone_combo: QComboBox | None = None
        self._audience_combo: QComboBox | None = None
        self._generate_button: QPushButton | None = None
        self._copy_button: QPushButton | None = None
        self._insert_button: QPushButton | None = None
        self._result_view: QTextEdit | None = None
        self._status_label: QLabel | None = None
        self._second_line_checkbox: QCheckBox | None = None

        self._build_ui()
        self._apply_case_state()
        self._refresh_template_list()

    # ───────────────────── UI helpers ────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Generador de correos con IA")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        header.addWidget(title)
        header.addStretch()

        self._second_line_checkbox = QCheckBox("Modo 2nd Line")
        self._second_line_checkbox.toggled.connect(self._on_second_line_toggled)
        header.addWidget(self._second_line_checkbox)
        layout.addLayout(header)

        layout.addWidget(QLabel("Selecciona una plantilla"))
        self._template_list = QListWidget()
        self._template_list.setSelectionMode(QListWidget.SingleSelection)
        self._template_list.currentItemChanged.connect(self._on_template_changed)
        layout.addWidget(self._template_list)

        self._template_description = QLabel()
        self._template_description.setWordWrap(True)
        layout.addWidget(self._template_description)

        tone_row = QHBoxLayout()
        tone_row.addWidget(QLabel("Tono"))
        self._tone_combo = QComboBox()
        for label, value in TONE_OPTIONS:
            self._tone_combo.addItem(label, value)
        self._tone_combo.currentIndexChanged.connect(self._on_tone_changed)
        tone_row.addWidget(self._tone_combo)

        tone_row.addSpacing(12)
        tone_row.addWidget(QLabel("Audiencia"))
        self._audience_combo = QComboBox()
        for label, value in AUDIENCE_OPTIONS:
            self._audience_combo.addItem(label, value)
        self._audience_combo.currentIndexChanged.connect(self._on_audience_changed)
        tone_row.addWidget(self._audience_combo)
        tone_row.addStretch()
        layout.addLayout(tone_row)

        layout.addWidget(QLabel("Prompt personalizado"))
        self._prompt_editor = QPlainTextEdit()
        self._prompt_editor.setPlaceholderText("Instrucciones que se enviarán al modelo")
        self._prompt_editor.textChanged.connect(self._on_prompt_changed)
        layout.addWidget(self._prompt_editor)

        button_row = QHBoxLayout()
        self._generate_button = QPushButton("Generar correo")
        self._generate_button.clicked.connect(self._on_generate_clicked)
        button_row.addWidget(self._generate_button)

        self._copy_button = QPushButton("Copiar resultado")
        self._copy_button.clicked.connect(self._on_copy_clicked)
        self._copy_button.setEnabled(False)
        button_row.addWidget(self._copy_button)

        self._insert_button = QPushButton("Insertar en el caso")
        self._insert_button.clicked.connect(self._on_insert_clicked)
        self._insert_button.setEnabled(False)
        button_row.addWidget(self._insert_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        layout.addWidget(QLabel("Resultado"))
        self._result_view = QTextEdit()
        self._result_view.setReadOnly(True)
        layout.addWidget(self._result_view)

        self._status_label = QLabel()
        layout.addWidget(self._status_label)

    def refresh_case(self, case: CaseData) -> None:
        """Synchronise the UI with the latest case state."""

        self._case = case
        self._apply_case_state()
        self._refresh_template_list()

    def _apply_case_state(self) -> None:
        if not self._second_line_checkbox:
            return
        self._second_line_checkbox.setChecked(self._case.email_second_line_mode)

        if self._tone_combo:
            tone = self._case.email_tone or TONE_OPTIONS[0][1]
            index = self._tone_combo.findData(tone)
            self._tone_combo.setCurrentIndex(index if index >= 0 else 0)

        if self._audience_combo:
            audience = self._case.email_audience or AUDIENCE_OPTIONS[0][1]
            index = self._audience_combo.findData(audience)
            self._audience_combo.setCurrentIndex(index if index >= 0 else 0)

        if self._result_view and self._case.email_last_body:
            self._result_view.setPlainText(self._case.email_last_body)
            if self._copy_button:
                self._copy_button.setEnabled(True)
            if self._insert_button:
                self._insert_button.setEnabled(True)

    def _refresh_template_list(self) -> None:
        if not self._template_list:
            return

        second_line = self._second_line_checkbox.isChecked() if self._second_line_checkbox else False
        available = [
            t
            for t in TEMPLATE_DEFINITIONS
            if second_line or not t.second_line_only
        ]

        self._template_list.blockSignals(True)
        self._template_list.clear()
        for template in available:
            item = QListWidgetItem(f"{template.icon} {template.label}\n{template.description}")
            item.setData(Qt.UserRole, template.value)
            item.setData(Qt.UserRole + 1, template)
            self._template_list.addItem(item)
        self._template_list.blockSignals(False)

        desired = self._case.email_selected_template
        if desired not in {t.value for t in available} and available:
            desired = available[0].value
        self._select_template(desired)

    def _select_template(self, value: str) -> None:
        if not self._template_list or not value:
            if self._template_list and self._template_list.count():
                self._template_list.setCurrentRow(0)
            return
        for row in range(self._template_list.count()):
            item = self._template_list.item(row)
            if item.data(Qt.UserRole) == value:
                self._template_list.setCurrentRow(row)
                return
        if self._template_list.count():
            self._template_list.setCurrentRow(0)

    # ───────────────────── Event handlers ───────────────────────
    def _on_second_line_toggled(self, checked: bool) -> None:
        self._case.email_second_line_mode = bool(checked)
        self._refresh_template_list()

    def _on_template_changed(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        if not current or not self._prompt_editor:
            return
        template = current.data(Qt.UserRole + 1)
        if not isinstance(template, TemplateDefinition):
            return
        self._case.email_selected_template = template.value
        if self._template_description:
            self._template_description.setText(template.description)
        prompt = self._build_prompt(template)
        self._set_prompt_text(prompt)

    def _on_tone_changed(self) -> None:
        if not self._tone_combo:
            return
        self._case.email_tone = self._tone_combo.currentData() or "neutral"
        self._rebuild_prompt_if_pristine()

    def _on_audience_changed(self) -> None:
        if not self._audience_combo:
            return
        self._case.email_audience = self._audience_combo.currentData() or "customer"
        self._rebuild_prompt_if_pristine()

    def _on_prompt_changed(self) -> None:
        if self._setting_prompt or not self._prompt_editor:
            return
        text = self._prompt_editor.toPlainText()
        self._case.email_custom_prompt = text

    def _on_generate_clicked(self) -> None:
        if not self._prompt_editor or not self._generate_button:
            return
        template = self._current_template()
        if not template:
            return
        prompt = self._prompt_editor.toPlainText().strip()
        tone = self._tone_combo.currentData() if self._tone_combo else "neutral"
        audience = self._audience_combo.currentData() if self._audience_combo else "customer"
        if not prompt and not template.use_generate_email:
            QMessageBox.information(self, "IA", "Define un prompt para generar el correo.")
            return

        self._generate_button.setEnabled(False)
        if self._status_label:
            self._status_label.setText("Generando correo…")

        def _worker() -> str:
            if template.use_generate_email and prompt == self._auto_prompt_text:
                return self._ai_client.generate_email_body(
                    self._case,
                    tone=tone or "neutral",
                    audience=audience or "customer",
                )
            prompt_text = prompt or self._build_prompt(template)
            return self._ai_client.invoke_completion(prompt_text)

        def _on_success(result: str) -> None:
            text = (result or "").strip()
            if self._result_view:
                self._result_view.setPlainText(text)
            self._case.email_last_body = text
            self._case.email_draft = text
            if self._copy_button:
                self._copy_button.setEnabled(bool(text))
            if self._insert_button:
                self._insert_button.setEnabled(bool(text))
            if self._status_label:
                self._status_label.setText("Borrador listo para copiar o insertar")
            if self._generate_button:
                self._generate_button.setEnabled(True)

        def _on_error(exc: Exception) -> None:
            if self._status_label:
                self._status_label.setText("Error al generar el correo")
            if self._generate_button:
                self._generate_button.setEnabled(True)
            QMessageBox.warning(self, "IA", f"No se pudo generar el correo: {exc}")

        run_in_threadpool(
            _worker,
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    def _on_copy_clicked(self) -> None:
        if not self._result_view:
            return
        text = self._result_view.toPlainText().strip()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._case.email_last_body = text
        if self._status_label:
            self._status_label.setText("Correo copiado al portapapeles")

    def _on_insert_clicked(self) -> None:
        if not self._result_view:
            return
        text = self._result_view.toPlainText().strip()
        if not text:
            return
        self._case.email_draft = text
        if self._status_label:
            self._status_label.setText("Correo guardado en el caso")

    # ───────────────────── Helper methods ───────────────────────
    def _current_template(self) -> TemplateDefinition | None:
        if not self._template_list:
            return None
        item = self._template_list.currentItem()
        if not item:
            return None
        template = item.data(Qt.UserRole + 1)
        return template if isinstance(template, TemplateDefinition) else None

    def _build_prompt(self, template: TemplateDefinition) -> str:
        tone = self._tone_combo.currentData() if self._tone_combo else "neutral"
        audience = self._audience_combo.currentData() if self._audience_combo else "customer"
        if template.prompt_builder:
            return template.prompt_builder(self._case, str(tone), str(audience))
        return _default_email_prompt(self._case, str(tone), str(audience))

    def _set_prompt_text(self, text: str) -> None:
        if not self._prompt_editor:
            return
        self._setting_prompt = True
        self._prompt_editor.setPlainText(text)
        self._setting_prompt = False
        self._auto_prompt_text = text
        self._case.email_custom_prompt = text

    def _rebuild_prompt_if_pristine(self) -> None:
        if not self._prompt_editor:
            return
        current_text = self._prompt_editor.toPlainText()
        template = self._current_template()
        if not template:
            return
        new_prompt = self._build_prompt(template)
        if current_text == self._auto_prompt_text:
            self._set_prompt_text(new_prompt)
        else:
            self._auto_prompt_text = new_prompt

