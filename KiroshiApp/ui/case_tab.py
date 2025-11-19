"""Case tab form for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Dict, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.model import (
    PRIORITY_OPTIONS,
    CaseData,
    RemoteSessionEntry,
    TrackingData,
)


@dataclass
class FieldConfig:
    """Metadata describing a form field."""

    name: str
    label: str
    kind: str = "text"  # text | multiline | bool | combo | spin
    options: Sequence[str] | None = None
    target: str = "case"  # case | tracking
    placeholder: str = ""


class RemoteSessionWidget(QGroupBox):
    """Widget that represents a single remote troubleshooting session."""

    changed = Signal()
    removed = Signal(str)

    def __init__(self, entry: RemoteSessionEntry, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        self.setTitle(self._session_title(index))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        header_layout = QHBoxLayout()

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("Título de la sesión")
        self.title_edit.setText(entry.title)
        self.title_edit.textChanged.connect(self._on_changed)
        header_layout.addWidget(QLabel("Título:", self))
        header_layout.addWidget(self.title_edit)

        remove_button = QPushButton("Eliminar", self)
        remove_button.clicked.connect(lambda: self.removed.emit(self.entry.session_id))
        header_layout.addWidget(remove_button)

        layout.addLayout(header_layout)

        self.notes_edit = QPlainTextEdit(self)
        self.notes_edit.setPlaceholderText("Notas de la sesión")
        self.notes_edit.setPlainText(entry.notes)
        self.notes_edit.textChanged.connect(self._on_changed)
        layout.addWidget(self.notes_edit)

    def _session_title(self, index: int) -> str:
        return self.entry.display_title(index)

    def update_index(self, index: int) -> None:
        self.setTitle(self._session_title(index))

    def _on_changed(self) -> None:
        self.entry.title = self.title_edit.text()
        self.entry.notes = self.notes_edit.toPlainText()
        self.entry.touch()
        self.changed.emit()


@dataclass
class _SectionState:
    name: str
    group: QGroupBox
    content: QWidget
    progress_bar: QProgressBar
    fields: List[str]
    minimum_required: int


class CaseTab(QWidget):
    """Form-based widget that captures case information."""

    caseChanged = Signal(CaseData)
    hotkeySelectionChanged = Signal(bool)
    exportRequested = Signal(CaseData)

    def __init__(
        self,
        case: CaseData | None = None,
        parent: QWidget | None = None,
        *,
        hotkeys_available: bool = True,
        hotkey_unavailable_reason: str = "",
    ) -> None:
        super().__init__(parent)
        self._case = case or CaseData()
        self._syncing = False
        self._hotkeys_available = hotkeys_available
        self._hotkey_unavailable_reason = hotkey_unavailable_reason.strip()

        self._case_fields: dict[str, QWidget] = {}
        self._tracking_fields: dict[str, QWidget] = {}
        self._remote_session_widgets: List[RemoteSessionWidget] = []
        self._sections: Dict[str, _SectionState] = {}
        self._section_order: List[str] = []

        self._build_ui()
        self._populate_from_case()

    # ──────────────────── UI builders ────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_label = QLabel("Case overview", self)
        title_label.setToolTip(
            "Completa cada sección en orden: cabecera, llamada, notas internas,\n"
            "conclusión, encuesta y sesiones remotas. Las siguientes secciones\n"
            "se habilitarán cuando la previa tenga la información mínima."
        )
        header.addWidget(title_label)
        header.addStretch(1)
        self._hotkey_checkbox = QCheckBox("Use this case for global clipboard hotkeys", self)
        self._hotkey_checkbox.setToolTip(
            "Activa el caso para los atajos globales de portapapeles."
        )
        self._hotkey_checkbox.toggled.connect(self._on_hotkey_toggled)
        if not self._hotkeys_available:
            suffix = " (no disponible)"
            self._hotkey_checkbox.setText(f"Usar para atajos de portapapeles{suffix}")
            tooltip = (
                self._hotkey_unavailable_reason
                or "Los atajos globales requieren qhotkey o keyboard instalados."
            )
            self._hotkey_checkbox.setToolTip(tooltip)
            self._hotkey_checkbox.setEnabled(False)
        header.addWidget(self._hotkey_checkbox)
        layout.addLayout(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        container = QWidget(scroll)
        scroll.setWidget(container)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(16)

        container_layout.addWidget(
            self._build_header_section(
                title="Cabecera",
                subtitle="Identificación del caso y resumen rápido.",
                name="header",
                minimum_required=3,
            )
        )
        container_layout.addWidget(
            self._build_call_section(
                title="Llamada",
                subtitle="Datos de contacto y contexto de la llamada inicial.",
                name="call",
                minimum_required=2,
            )
        )
        container_layout.addWidget(
            self._build_internal_notes_section(
                title="Notas internas",
                subtitle="Bitácora interna, enlaces y hallazgos previos.",
                name="internal_notes",
                minimum_required=1,
            )
        )
        container_layout.addWidget(
            self._build_conclusion_section(
                title="Conclusión",
                subtitle="Cierre técnico, RCA y resumen para terceros.",
                name="conclusion",
                minimum_required=1,
            )
        )
        container_layout.addWidget(
            self._build_survey_section(
                title="Encuesta / Cuestionario",
                subtitle="Seguimiento con el cliente y notas de cuestionarios.",
                name="survey",
                minimum_required=1,
            )
        )
        container_layout.addWidget(
            self._build_remote_sessions_section(
                title="Sesiones remotas",
                subtitle="Historial de accesos remotos y observaciones.",
                name="remote_sessions",
                minimum_required=1,
            )
        )
        container_layout.addWidget(self._build_tracking_section())
        container_layout.addWidget(self._build_hardware_section())
        container_layout.addStretch(1)

    def _create_section(
        self, title: str, subtitle: str, name: str, *, minimum_required: int
    ) -> tuple[QGroupBox, QWidget, QVBoxLayout]:
        group = QGroupBox(title, self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        subtitle_label = QLabel(subtitle, group)
        subtitle_label.setObjectName("subtitle")
        subtitle_label.setStyleSheet("color: #666; font-size: 11px;")
        subtitle_label.setToolTip(subtitle)
        header_row.addWidget(subtitle_label, stretch=1)

        progress = QProgressBar(group)
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setFormat("%p% completado")
        progress.setFixedHeight(14)
        header_row.addWidget(progress)
        layout.addLayout(header_row)

        content = QWidget(group)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        layout.addWidget(content)

        section_state = _SectionState(
            name=name,
            group=group,
            content=content,
            progress_bar=progress,
            fields=[],
            minimum_required=minimum_required,
        )
        self._sections[name] = section_state
        self._section_order.append(name)
        return group, content, content_layout

    def _register_field(self, section_name: str, field_name: str, widget: QWidget) -> None:
        self._case_fields[field_name] = widget
        self._sections[section_name].fields.append(field_name)

    def _build_header_section(
        self, *, title: str, subtitle: str, name: str, minimum_required: int
    ) -> QWidget:
        group, content, content_layout = self._create_section(title, subtitle, name, minimum_required=minimum_required)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        content_layout.addLayout(form)

        header_fields: list[tuple[str, str, bool]] = [
            ("company_name", "Company name", False),
            ("case_id", "Case ID", False),
            ("subscription_id", "Subscription ID", False),
            ("application_version", "Application version", False),
            ("kiroshi_version", "Kiroshi version", False),
            ("brief_description", "Brief description", True),
            ("description", "Full description", True),
        ]

        for field_name, label, multiline in header_fields:
            widget: QWidget
            if multiline:
                editor = QPlainTextEdit(group)
                editor.setPlaceholderText("Añade contexto o una descripción ampliada")
                editor.textChanged.connect(
                    partial(self._on_multiline_changed, field_name, editor)
                )
                widget = editor
            else:
                editor = QLineEdit(group)
                editor.setPlaceholderText("Completa el campo de cabecera")
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._register_field(name, field_name, widget)
            form.addRow(label + ":", widget)

        return group

    def _build_call_section(
        self, *, title: str, subtitle: str, name: str, minimum_required: int
    ) -> QWidget:
        group, content, content_layout = self._create_section(title, subtitle, name, minimum_required=minimum_required)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        content_layout.addLayout(form)

        call_fields: list[tuple[str, str, bool]] = [
            ("caller_name", "Caller name", False),
            ("phone_number", "Phone number", False),
            ("phone_description", "Phone description", True),
            ("dongle_number", "Dongle number", False),
            ("teamviewer_id", "TeamViewer ID", False),
            ("teamviewer_password", "TeamViewer password", False),
            ("email", "Email", False),
            ("contact_name", "Contact name", False),
            ("office_ph", "Office phone", False),
            ("direct_ph", "Direct phone", False),
            ("best_time", "Best time to call", False),
        ]

        for field_name, label, multiline in call_fields:
            if multiline:
                editor = QPlainTextEdit(group)
                editor.setPlaceholderText("Detalles relevantes de la llamada")
                editor.textChanged.connect(
                    partial(self._on_multiline_changed, field_name, editor)
                )
                widget: QWidget = editor
            else:
                editor = QLineEdit(group)
                editor.setPlaceholderText("Información de contacto y llamada")
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._register_field(name, field_name, widget)
            form.addRow(label + ":", widget)

        return group

    def _build_internal_notes_section(
        self, *, title: str, subtitle: str, name: str, minimum_required: int
    ) -> QWidget:
        group, content, content_layout = self._create_section(title, subtitle, name, minimum_required=minimum_required)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        content_layout.addLayout(form)

        notes_fields: list[tuple[str, str]] = [
            ("internal_helpjuice", "Internal Helpjuice"),
            ("internal_logs", "Internal logs"),
            ("additional_info", "Additional info"),
            ("remote_steps", "Remote steps summary"),
        ]

        for field_name, label in notes_fields:
            editor = QPlainTextEdit(group)
            editor.setPlaceholderText("Notas internas y enlaces de referencia")
            if field_name == "remote_steps":
                editor.setReadOnly(True)
                editor.setToolTip(
                    "Se genera automáticamente a partir de las sesiones remotas."
                )
            editor.textChanged.connect(
                partial(self._on_multiline_changed, field_name, editor)
            )
            self._register_field(name, field_name, editor)
            form.addRow(label + ":", editor)

        return group

    def _build_conclusion_section(
        self, *, title: str, subtitle: str, name: str, minimum_required: int
    ) -> QWidget:
        group, content, content_layout = self._create_section(title, subtitle, name, minimum_required=minimum_required)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        content_layout.addLayout(form)

        conclusion_fields: list[tuple[str, str, bool]] = [
            ("solution", "Solution", True),
            ("root_cause", "Root cause", True),
            ("repro_steps", "Repro steps", True),
            ("third_line_hj_article", "3rd line HJ article", False),
            (
                "third_line_troubleshoot_summary",
                "3rd line troubleshoot summary",
                True,
            ),
            ("third_line_comments", "3rd line comments", True),
            ("third_line_reseller_name", "Reseller name", False),
            ("third_line_reseller_phone", "Reseller phone", False),
            ("third_line_reseller_phone_alt", "Reseller phone (alt)", False),
            ("third_line_reseller_email", "Reseller email", False),
            ("third_line_clinic_rep_name", "Clinic rep name", False),
            ("third_line_clinic_rep_phone", "Clinic rep phone", False),
            ("third_line_clinic_rep_phone_alt", "Clinic rep phone (alt)", False),
            ("third_line_tv_id", "Clinic TV ID", False),
            ("third_line_tv_password", "Clinic TV password", False),
            ("third_line_unite_pin", "Unite PIN", False),
        ]

        for field_name, label, multiline in conclusion_fields:
            if multiline:
                editor = QPlainTextEdit(group)
                editor.setPlaceholderText("Conclusiones y RCA detallada")
                editor.textChanged.connect(
                    partial(self._on_multiline_changed, field_name, editor)
                )
                widget: QWidget = editor
            else:
                editor = QLineEdit(group)
                editor.setPlaceholderText("Dato de cierre o contacto externo")
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._register_field(name, field_name, widget)
            form.addRow(label + ":", widget)

        return group

    def _build_survey_section(
        self, *, title: str, subtitle: str, name: str, minimum_required: int
    ) -> QWidget:
        group, content, content_layout = self._create_section(title, subtitle, name, minimum_required=minimum_required)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        content_layout.addLayout(form)

        survey_fields: list[tuple[str, str, str]] = [
            ("survey_link", "Survey link", "text"),
            ("request_issue", "Request issue", "multiline"),
            ("patterson", "Patterson", "text"),
            ("straumann", "Straumann", "text"),
            ("esc_name", "ESC name", "text"),
            ("esc_ph", "ESC phone", "text"),
            ("esc_email", "ESC email", "text"),
            ("email_selected_template", "Email template", "text"),
            ("email_custom_prompt", "Email custom prompt", "multiline"),
            ("email_last_body", "Last email body", "multiline"),
            ("email_draft", "Email draft", "multiline"),
        ]

        for field_name, label, kind in survey_fields:
            if kind == "multiline":
                editor = QPlainTextEdit(group)
                editor.setPlaceholderText("Detalles de seguimiento o cuestionario")
                editor.textChanged.connect(
                    partial(self._on_multiline_changed, field_name, editor)
                )
                widget: QWidget = editor
            else:
                editor = QLineEdit(group)
                editor.setPlaceholderText("Enlace o dato de seguimiento")
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._register_field(name, field_name, widget)
            form.addRow(label + ":", widget)

        email_tone_combo = QComboBox(group)
        email_tone_combo.addItems(["neutral", "friendly", "formal", "concise"])
        email_tone_combo.currentTextChanged.connect(self._on_email_tone_changed)
        self._register_field(name, "email_tone", email_tone_combo)
        form.addRow("Email tone:", email_tone_combo)

        email_audience_combo = QComboBox(group)
        email_audience_combo.addItems(["customer", "reseller", "internal"])
        email_audience_combo.currentTextChanged.connect(self._on_email_audience_changed)
        self._register_field(name, "email_audience", email_audience_combo)
        form.addRow("Email audience:", email_audience_combo)

        email_second_line_checkbox = QCheckBox("Second line mode", group)
        email_second_line_checkbox.toggled.connect(self._on_email_second_line_toggled)
        self._register_field(name, "email_second_line_mode", email_second_line_checkbox)
        form.addRow(email_second_line_checkbox)

        return group

    def _build_call_section(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._tracking_active_checkbox = QCheckBox("Track this case", group)
        self._tracking_active_checkbox.setToolTip(
            "Activa el seguimiento solo si el caso debe aparecer en reportes."
        )
        self._tracking_active_checkbox.toggled.connect(self._on_tracking_active_toggled)
        layout.addWidget(self._tracking_active_checkbox)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        configs = [
            FieldConfig("internal_helpjuice", "Artículos internos"),
            FieldConfig("internal_logs", "Logs internos", kind="multiline"),
            FieldConfig("additional_info", "Notas adicionales", kind="multiline"),
            FieldConfig("include_hardware_fields", "Incluir campos de hardware", kind="bool"),
            FieldConfig("root_cause", "Causa raíz", kind="multiline"),
            FieldConfig("repro_steps", "Pasos para reproducir", kind="multiline"),
        ]
        self._create_fields(form, configs, section="notes")
        layout.addLayout(form)

        hardware_group = QGroupBox("Diagnóstico de hardware", container)
        self._hardware_group = hardware_group
        hardware_layout = QFormLayout(hardware_group)
        hardware_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        hardware_configs = [
            FieldConfig("hardware_test", "Prueba de hardware", kind="multiline"),
            FieldConfig("service_tag", "Service tag"),
            FieldConfig("pc_model", "Modelo PC"),
            FieldConfig("windows_version", "Versión de Windows"),
            FieldConfig("bios_version", "Versión BIOS"),
            FieldConfig("graphics_card", "Tarjeta gráfica"),
            FieldConfig("processor", "Procesador"),
            FieldConfig("warranty", "Garantía"),
            FieldConfig("scanner_sn", "Scanner S/N"),
            FieldConfig("base_sn", "Base S/N"),
            FieldConfig("trios_module_version", "Versión módulo TRIOS"),
            FieldConfig("scanner_previous_replacements", "Reemplazos previos", kind="spin"),
            FieldConfig("scanner_accidental_damage", "Daño accidental"),
            FieldConfig("dell_issue_start_date", "Fecha de inicio"),
            FieldConfig("dell_command_updates_status", "Command Updates"),
            FieldConfig("dell_power_options_setup", "Opciones de energía"),
            FieldConfig("dell_optimizer_setup", "Optimizer"),
            FieldConfig("dell_intel_ppm_installed", "Intel PPM"),
            FieldConfig("dell_cpu_speed_or_throttling", "Velocidad/Throttling CPU"),
            FieldConfig("dell_gpu_usage_integrated", "Uso GPU integrada"),
            FieldConfig("dell_gpu_usage_dedicated", "Uso GPU dedicada"),
            FieldConfig("dell_cpu_utilization", "Uso CPU"),
            FieldConfig("dell_benchmark_results", "Resultados benchmark", kind="multiline"),
            FieldConfig("dell_ultra_resolution_support", "Soporte ultra resolución"),
            FieldConfig("dell_gpu_driver_versions", "Drivers GPU"),
            FieldConfig("dell_reliability_monitor_results", "Monitor de fiabilidad", kind="multiline"),
            FieldConfig("dell_diagnostics_results", "Diagnósticos", kind="multiline"),
            FieldConfig("dell_windows_reimaged", "Windows reinstalado"),
            FieldConfig("clinic_name", "Clínica"),
            FieldConfig("clinic_contact_name", "Contacto clínica"),
            FieldConfig("clinic_contact_phone", "Teléfono clínica"),
            FieldConfig("clinic_contact_email", "Email clínica"),
            FieldConfig("clinic_address_line_1", "Dirección 1"),
            FieldConfig("clinic_address_line_2", "Dirección 2"),
            FieldConfig("clinic_city", "Ciudad"),
            FieldConfig("clinic_state", "Estado"),
            FieldConfig("clinic_postal_code", "Código postal"),
            FieldConfig("customer_trios_only", "Cliente solo TRIOS", kind="bool"),
            FieldConfig("support_fee_accepted", "Fee de soporte aceptado", kind="bool"),
        ]
        self._create_fields(hardware_layout, hardware_configs, section="notes")
        layout.addWidget(hardware_group)
        return container

    def _build_conclusion_section(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        configs = [
            FieldConfig("solution", "Solución propuesta", kind="multiline"),
            FieldConfig("third_line_hj_article", "Artículo HJ 3L"),
            FieldConfig("third_line_troubleshoot_summary", "Resumen 3L", kind="multiline"),
            FieldConfig("third_line_comments", "Comentarios 3L", kind="multiline"),
            FieldConfig("third_line_reseller_name", "Reseller"),
            FieldConfig("third_line_reseller_phone", "Teléfono reseller"),
            FieldConfig("third_line_reseller_phone_alt", "Teléfono alterno reseller"),
            FieldConfig("third_line_reseller_email", "Email reseller"),
            FieldConfig("third_line_clinic_rep_name", "Representante clínica"),
            FieldConfig("third_line_clinic_rep_phone", "Teléfono representante"),
            FieldConfig("third_line_clinic_rep_phone_alt", "Teléfono alterno representante"),
            FieldConfig("third_line_tv_id", "TeamViewer 3L"),
            FieldConfig("third_line_tv_password", "Password 3L"),
            FieldConfig("third_line_unite_pin", "PIN Unite"),
            FieldConfig("esc_name", "Contacto ESC"),
            FieldConfig("esc_ph", "Teléfono ESC"),
            FieldConfig("esc_email", "Email ESC"),
            FieldConfig("remote_steps", "Resumen de pasos remotos", kind="multiline"),
        ]
        self._create_fields(form, configs, section="conclusion")
        return container

    def _build_survey_section(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    def _build_remote_sessions_section(
        self, *, title: str, subtitle: str, name: str, minimum_required: int
    ) -> QWidget:
        group, content, content_layout = self._create_section(title, subtitle, name, minimum_required=minimum_required)

        info = QLabel(
            "Completa las sesiones en orden. Se habilitarán cuando las secciones previas estén completas.",
            container,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._remote_sessions_container = QWidget(container)
        self._remote_sessions_layout = QVBoxLayout(self._remote_sessions_container)
        self._remote_sessions_layout.setContentsMargins(0, 0, 0, 0)
        self._remote_sessions_layout.setSpacing(8)
        content_layout.addWidget(self._remote_sessions_container)

        add_button = QPushButton("Add remote session", group)
        add_button.setToolTip("Registra nuevas conexiones remotas y apuntes.")
        add_button.clicked.connect(self._add_remote_session)
        content_layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

        self._register_field(name, "remote_sessions", self._remote_sessions_container)
        return group

    def _build_hardware_section(self) -> QWidget:
        group = QGroupBox("Hardware diagnostics", self)
        layout = QVBoxLayout(group)

        self._include_hardware_checkbox = QCheckBox("Include hardware issue fields", group)
        self._include_hardware_checkbox.toggled.connect(self._on_include_hardware_toggled)
        layout.addWidget(self._include_hardware_checkbox)

        self._hardware_fields_container = QWidget(group)
        hardware_form = QFormLayout(self._hardware_fields_container)
        hardware_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        hardware_config: list[tuple[str, str, str]] = [
            ("hardware_test", "Hardware test", "multiline"),
            ("service_tag", "Dell service tag", "text"),
            ("pc_model", "PC model", "text"),
            ("windows_version", "Windows version", "text"),
            ("bios_version", "BIOS version", "text"),
            ("graphics_card", "Graphics card", "text"),
            ("processor", "Processor", "text"),
            ("warranty", "Warranty", "text"),
            ("scanner_sn", "Scanner S/N", "text"),
            ("base_sn", "Base S/N", "text"),
            ("trios_module_version", "TRIOS module version", "text"),
            ("dongle_deployment_date", "Dongle deployment date", "text"),
            ("scanner_previous_replacements", "Scanner replacements", "spin"),
            ("scanner_accidental_damage", "Scanner accidental damage", "text"),
            ("dell_issue_start_date", "Issue start date", "text"),
            ("dell_command_updates_status", "Command Updates status", "text"),
            ("dell_power_options_setup", "Power options setup", "text"),
            ("dell_optimizer_setup", "Optimizer setup", "text"),
            ("dell_intel_ppm_installed", "Intel PPM installed", "text"),
            ("dell_cpu_speed_or_throttling", "CPU speed/throttling", "text"),
            ("dell_gpu_usage_integrated", "GPU usage (integrated)", "text"),
            ("dell_gpu_usage_dedicated", "GPU usage (dedicated)", "text"),
            ("dell_cpu_utilization", "CPU utilisation", "text"),
            ("dell_benchmark_results", "Benchmark results", "multiline"),
            ("dell_ultra_resolution_support", "Ultra resolution support", "text"),
            ("dell_gpu_driver_versions", "GPU driver versions", "text"),
            ("dell_reliability_monitor_results", "Reliability monitor", "multiline"),
            ("dell_diagnostics_results", "Diagnostics results", "multiline"),
            ("dell_windows_reimaged", "Windows reimaged", "text"),
            ("clinic_name", "Clinic name", "text"),
            ("clinic_contact_name", "Clinic contact name", "text"),
            ("clinic_contact_phone", "Clinic contact phone", "text"),
            ("clinic_contact_email", "Clinic contact email", "text"),
            ("clinic_address_line_1", "Clinic address line 1", "text"),
            ("clinic_address_line_2", "Clinic address line 2", "text"),
            ("clinic_city", "Clinic city", "text"),
            ("clinic_state", "Clinic state", "text"),
            ("clinic_postal_code", "Clinic postal code", "text"),
        ]

        for field_name, label, kind in hardware_config:
            if kind == "multiline":
                editor = QPlainTextEdit(self._hardware_fields_container)
                editor.textChanged.connect(partial(self._on_hardware_multiline_changed, field_name, editor))
                widget: QWidget = editor
            elif kind == "spin":
                spin = QSpinBox(self._hardware_fields_container)
                spin.setMinimum(0)
                spin.setMaximum(999)
                spin.valueChanged.connect(
                    partial(self._on_spin_changed, config.name, spin, config.target)
                )
                widget = spin
            elif kind == "checkbox":
                checkbox = QCheckBox(label, group)
                checkbox.setToolTip(tooltip)
                checkbox.toggled.connect(
                    partial(self._on_hardware_checkbox_toggled, field_name, checkbox)
                )
                widget = checkbox
                form.addRow(checkbox)
                self._hardware_fields[field_name] = widget
                continue
            else:
                editor = QLineEdit(self)
                editor.setPlaceholderText(config.placeholder or config.label)
                editor.textChanged.connect(
                    partial(self._on_text_changed, config.name, editor, config.target)
                )
                widget = editor

            if not isinstance(widget, QCheckBox):
                layout.addRow(config.label + ":", widget)
            self._register_field(config, widget, section)

    def _register_field(self, config: FieldConfig, widget: QWidget, section: str) -> None:
        key = f"{config.target}:{config.name}"
        if config.target == "tracking":
            self._tracking_fields[config.name] = widget
        else:
            self._fields[config.name] = widget
        self._sections[section]["fields"].append(key)

    # ──────────────────── Population helpers ────────────────────
    def _populate_from_case(self) -> None:
        self._syncing = True

        for field_name, widget in self._case_fields.items():
            value = getattr(self._case, field_name, "")
            if isinstance(widget, QLineEdit):
                widget.setText(value or "")
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText(value or "")
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                index = max(0, widget.findText(str(value or "")))
                widget.setCurrentIndex(index)

        tracking = self._case.tracking if isinstance(self._case.tracking, TrackingData) else TrackingData()
        for field_name, widget in self._tracking_fields.items():
            value = getattr(tracking, field_name, "") or ""
            if isinstance(widget, QLineEdit):
                widget.setText(value)
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(value))
                except (TypeError, ValueError):
                    widget.setValue(0)
            elif isinstance(widget, QComboBox):
                index = max(0, widget.findText(str(value) or PRIORITY_OPTIONS[0]))
                widget.setCurrentIndex(index)

        self._hotkey_checkbox.setChecked(bool(self._case.active_for_hotkeys))

        self._clear_remote_session_widgets()
        sessions = list(self._case.remote_sessions or [])
        if sessions:
            for entry in sessions:
                self._add_remote_session(entry, emit_changed=False)
        else:
            self._add_remote_session(RemoteSessionEntry(), emit_changed=False)
        self._sync_remote_sessions_from_widgets(emit_changed=False)
        self._update_sections_state()

        self._syncing = False
        self._update_remote_steps_summary()
        self._toggle_hardware_visibility()
        self._update_section_states()
        self._update_hotkey_buttons()

    # ──────────────────── Case mutators ────────────────────
    def _on_text_changed(self, field_name: str, editor: QLineEdit, target: str) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.text())
        self._after_field_change()

    def _on_multiline_changed(self, field_name: str, editor: QPlainTextEdit, target: str) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.toPlainText())
        self._after_field_change()

    def _on_combo_changed(self, field_name: str, combo: QComboBox, target: str, value: str) -> None:
        if self._syncing:
            return
        if target == "tracking":
            tracking = self._ensure_tracking()
            setattr(tracking, field_name, value)
        else:
            setattr(self._case, field_name, value)
        self._emit_case_changed()

    def _on_spin_changed(self, field_name: str, spin: QSpinBox, target: str, value: int) -> None:
        if self._syncing:
            return
        tracking = self._ensure_tracking()
        setattr(tracking, field_name, editor.text())
        self._after_field_change()

    def _on_bool_changed(self, field_name: str, checkbox: QCheckBox, target: str, checked: bool) -> None:
        if self._syncing:
            return
        tracking = self._ensure_tracking()
        tracking.priority = value
        self._after_field_change()

    def _on_hotkey_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._case.active_for_hotkeys = checked
        self.hotkeySelectionChanged.emit(checked)
        self._after_field_change()

    def _on_include_hardware_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._case.include_hardware_fields = checked
        self._hardware_fields_container.setVisible(checked)
        self._after_field_change()

    def _on_hardware_text_changed(self, field_name: str, editor: QLineEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.text())
        self._after_field_change()

    def _on_hardware_multiline_changed(self, field_name: str, editor: QPlainTextEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.toPlainText())
        self._after_field_change()

    def _on_hardware_spin_changed(self, field_name: str, spin: QSpinBox, value: int) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, int(value))
        self._after_field_change()

    def _set_case_flag(self, field_name: str, value: bool) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, bool(value))
        self._after_field_change()

    def _on_email_tone_changed(self, value: str) -> None:
        if self._syncing:
            return
        self._case.email_tone = value
        self._after_field_change()

    def _on_email_audience_changed(self, value: str) -> None:
        if self._syncing:
            return
        self._case.email_audience = value
        self._after_field_change()

    def _on_email_second_line_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._case.email_second_line_mode = checked
        self._after_field_change()

    def _ensure_tracking(self) -> TrackingData:
        if not isinstance(self._case.tracking, TrackingData):
            self._case.tracking = TrackingData()
        return self._case.tracking

    # ──────────────────── Remote sessions handling ────────────────────
    def _add_remote_session(
        self,
        entry: RemoteSessionEntry | None = None,
        *,
        emit_changed: bool = True,
    ) -> None:
        new_entry = entry or RemoteSessionEntry()
        widget = RemoteSessionWidget(new_entry, len(self._remote_session_widgets) + 1, self._remote_sessions_container)
        widget.changed.connect(self._on_remote_session_changed)
        widget.removed.connect(self._on_remote_session_removed)
        self._remote_sessions_layout.addWidget(widget)
        self._remote_session_widgets.append(widget)
        if emit_changed:
            self._sync_remote_sessions_from_widgets()

    def _clear_remote_session_widgets(self) -> None:
        for widget in self._remote_session_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self._remote_session_widgets.clear()

    def _on_remote_session_changed(self) -> None:
        if self._syncing:
            return
        self._sync_remote_sessions_from_widgets()

    def _on_remote_session_removed(self, session_id: str) -> None:
        if self._syncing:
            return
        for widget in list(self._remote_session_widgets):
            if widget.entry.session_id == session_id:
                self._remote_session_widgets.remove(widget)
                widget.setParent(None)
                widget.deleteLater()
        self._update_remote_session_titles()
        self._sync_remote_sessions_from_widgets()

    def _sync_remote_sessions_from_widgets(self, *, emit_changed: bool = True) -> None:
        self._case.remote_sessions = [widget.entry for widget in self._remote_session_widgets]
        self._update_remote_session_titles()
        self._update_remote_steps_summary()
        if emit_changed and not self._syncing:
            self._after_field_change()

    def _update_remote_session_titles(self) -> None:
        for idx, widget in enumerate(self._remote_session_widgets, start=1):
            widget.update_index(idx)

    def _update_remote_steps_summary(self) -> None:
        lines: List[str] = []
        for idx, entry in enumerate(self._case.remote_sessions, start=1):
            title = entry.display_title(idx)
            notes = entry.notes.strip()
            lines.append(f"{title}: {notes}" if notes else title)
        self._case.remote_steps = "\n\n".join(lines).strip()
        remote_widget = self._case_fields.get("remote_steps")
        if isinstance(remote_widget, QPlainTextEdit):
            previous_syncing = self._syncing
            self._syncing = True
            remote_widget.setPlainText(self._case.remote_steps)
            self._syncing = previous_syncing

    def _after_field_change(self) -> None:
        if self._syncing:
            return
        self._update_sections_state()
        self._emit_case_changed()

    def _update_sections_state(self) -> None:
        previous_complete = True
        for name in self._section_order:
            section = self._sections[name]
            filled, total = self._compute_section_completion(section)
            percent = int((filled / total) * 100) if total else 0
            section.progress_bar.setValue(percent)
            is_complete = filled >= section.minimum_required
            allowed = previous_complete
            section.group.setEnabled(allowed)
            section.content.setVisible(allowed)
            status_tooltip = (
                "Se habilita al completar la sección previa con información mínima."
            )
            section.group.setToolTip(status_tooltip)
            previous_complete = is_complete

    def _compute_section_completion(self, section: _SectionState) -> tuple[int, int]:
        filled = 0
        total = 0
        for field_name in section.fields:
            widget = self._case_fields.get(field_name)
            if widget is None:
                continue
            if field_name == "remote_sessions":
                filled += self._remote_sessions_completion_count()
                total += max(1, len(self._case.remote_sessions))
                continue
            total += 1
            if isinstance(widget, QLineEdit):
                if bool(widget.text().strip()):
                    filled += 1
            elif isinstance(widget, QPlainTextEdit):
                if bool(widget.toPlainText().strip()):
                    filled += 1
            elif isinstance(widget, QCheckBox):
                if widget.isChecked():
                    filled += 1
            elif isinstance(widget, QComboBox):
                if bool(widget.currentText().strip()):
                    filled += 1
            elif isinstance(widget, QSpinBox):
                if widget.value() > 0:
                    filled += 1
        return filled, total

    def _remote_sessions_completion_count(self) -> int:
        completed = 0
        for entry in self._case.remote_sessions:
            if entry.title.strip() or entry.notes.strip():
                completed += 1
        return completed

    # ──────────────────── Section helpers ────────────────────
    def _toggle_hardware_visibility(self) -> None:
        include = bool(self._case.include_hardware_fields)
        if self._hardware_group:
            self._hardware_group.setVisible(include)

    def _update_hotkey_buttons(self) -> None:
        enabled = self._hotkeys_available and bool(self._case.active_for_hotkeys)
        for section in self._section_order:
            button: QPushButton | None = self._sections[section].get("hotkey")  # type: ignore[index]
            if button:
                button.setEnabled(enabled)

    def _copy_section_to_clipboard(self, section: str) -> None:
        lines: List[str] = []
        for key in self._sections.get(section, {}).get("fields", []):
            target, field_name = key.split(":", 1)
            value = getattr(self._case.tracking if target == "tracking" else self._case, field_name, "")
            text = str(value).strip()
            if text:
                lines.append(f"{field_name}: {text}")
        if section == "remote":
            for idx, entry in enumerate(self._case.remote_sessions, start=1):
                summary = entry.notes.strip() or entry.title.strip()
                if summary:
                    lines.append(f"Sesión {idx}: {summary}")
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))

    def _section_progress(self, section: str) -> tuple[int, int]:
        keys = self._sections.get(section, {}).get("fields", [])
        filled = 0
        total = 0
        for key in keys:
            target, field_name = key.split(":", 1)
            value = getattr(self._case.tracking if target == "tracking" else self._case, field_name, "")
            if field_name.startswith("dell_") or field_name in {
                "hardware_test",
                "service_tag",
                "pc_model",
                "windows_version",
                "bios_version",
                "graphics_card",
                "processor",
                "warranty",
                "scanner_sn",
                "base_sn",
                "trios_module_version",
                "scanner_previous_replacements",
                "scanner_accidental_damage",
                "clinic_name",
                "clinic_contact_name",
                "clinic_contact_phone",
                "clinic_contact_email",
                "clinic_address_line_1",
                "clinic_address_line_2",
                "clinic_city",
                "clinic_state",
                "clinic_postal_code",
                "customer_trios_only",
                "support_fee_accepted",
            } and not self._case.include_hardware_fields:
                continue
            total += 1
            if isinstance(value, bool):
                if value:
                    filled += 1
            elif isinstance(value, int):
                if value > 0:
                    filled += 1
            elif str(value).strip():
                filled += 1
        if section == "remote":
            session_total = max(1, len(self._case.remote_sessions) * 2)
            session_filled = 0
            for entry in self._case.remote_sessions:
                if entry.title.strip():
                    session_filled += 1
                if entry.notes.strip():
                    session_filled += 1
            total += session_total
            filled += session_filled
        return filled, max(total, 1)

    def _update_section_states(self) -> None:
        for section in self._section_order:
            filled, total = self._section_progress(section)
            progress: QProgressBar | None = self._sections[section]["progress"]  # type: ignore[index]
            if progress:
                progress.setRange(0, total)
                progress.setValue(filled)
            group: QGroupBox = self._sections[section]["group"]  # type: ignore[index]
            group.setEnabled(True)

        previous_complete = True
        for section in self._section_order:
            group: QGroupBox = self._sections[section]["group"]  # type: ignore[index]
            if not previous_complete and section != self._section_order[0]:
                group.setEnabled(False)
            filled, total = self._section_progress(section)
            previous_complete = filled >= total and total > 0

    # ──────────────────── Public API ────────────────────
    def set_case(self, case: CaseData) -> None:
        self._case = case
        self._populate_from_case()

    def case(self) -> CaseData:
        return self._case

    # ──────────────────── Signal helpers ────────────────────
    def _emit_case_changed(self) -> None:
        if self._syncing:
            return
        self._update_section_states()
        self.caseChanged.emit(self._case)


__all__ = ["CaseTab"]
