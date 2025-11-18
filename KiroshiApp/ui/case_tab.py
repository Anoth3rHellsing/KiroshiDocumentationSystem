"""Case tab form for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable, Iterable, List, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
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


class CaseTab(QWidget):
    """Form-based widget that captures case information."""

    caseChanged = Signal(CaseData)
    hotkeySelectionChanged = Signal(bool)

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

        self._fields: dict[str, QWidget] = {}
        self._tracking_fields: dict[str, QWidget] = {}
        self._remote_session_widgets: List[RemoteSessionWidget] = []
        self._hardware_group: QGroupBox | None = None
        self._section_order = [
            "header",
            "call",
            "notes",
            "conclusion",
            "survey",
            "remote",
        ]
        self._sections: dict[str, dict[str, object]] = {}

        self._build_ui()
        self._populate_from_case()

    # ──────────────────── UI builders ────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Caso", self))
        header.addStretch(1)
        self._hotkey_checkbox = QCheckBox("Usar para atajos de portapapeles", self)
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

        section_builders: list[tuple[str, str, Callable[[], QWidget]]] = [
            ("header", "Cabecera", self._build_header_section),
            ("call", "Llamada telefónica", self._build_call_section),
            ("notes", "Notas internas", self._build_notes_section),
            ("conclusion", "Conclusión", self._build_conclusion_section),
            ("survey", "Encuesta y cuestionarios", self._build_survey_section),
            ("remote", "Sesiones remotas", self._build_remote_section),
        ]

        for key, title, builder in section_builders:
            group = self._wrap_section(title, key, builder())
            self._sections[key] = {
                "group": group,
                "progress": group.findChild(QProgressBar),
                "copy": group.findChild(QPushButton, f"copy-{key}"),
                "hotkey": group.findChild(QPushButton, f"hotkey-{key}"),
                "fields": [],
            }
            container_layout.addWidget(group)

        container_layout.addStretch(1)

    def _wrap_section(self, title: str, key: str, content: QWidget) -> QWidget:
        group = QGroupBox(title, self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        progress = QProgressBar(group)
        progress.setRange(0, 1)
        progress.setValue(0)
        progress.setFormat("Completado: %v/%m")
        layout.addWidget(progress)

        control_row = QHBoxLayout()
        control_row.addStretch(1)
        copy_button = QPushButton("Copiar sección", group)
        copy_button.setObjectName(f"copy-{key}")
        copy_button.clicked.connect(lambda: self._copy_section_to_clipboard(key))
        control_row.addWidget(copy_button)

        hotkey_button = QPushButton("Copiar (hotkey)", group)
        hotkey_button.setObjectName(f"hotkey-{key}")
        hotkey_button.setToolTip(
            "Disponible cuando el caso está marcado para atajos globales."
        )
        hotkey_button.clicked.connect(lambda: self._copy_section_to_clipboard(key))
        control_row.addWidget(hotkey_button)
        layout.addLayout(control_row)

        layout.addWidget(content)
        return group

    def _build_header_section(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        configs = [
            FieldConfig("company_name", "Empresa/Clínica"),
            FieldConfig("subscription_id", "ID de suscripción"),
            FieldConfig("case_id", "ID del caso"),
            FieldConfig("application_version", "Versión de la aplicación"),
            FieldConfig("kiroshi_version", "Versión de Kiroshi"),
            FieldConfig("last_modified", "Última modificación"),
            FieldConfig("brief_description", "Resumen breve", kind="multiline"),
            FieldConfig("description", "Descripción completa", kind="multiline"),
            FieldConfig("contact_name", "Nombre de contacto"),
            FieldConfig("caller_name", "Persona que llama"),
            FieldConfig("email", "Email"),
            FieldConfig("phone_number", "Teléfono principal"),
            FieldConfig("teamviewer_id", "TeamViewer ID"),
            FieldConfig("teamviewer_password", "TeamViewer password"),
            FieldConfig("dongle_number", "Número de dongle"),
            FieldConfig("dongle_deployment_date", "Fecha despliegue dongle"),
            FieldConfig("patterson", "Patterson"),
            FieldConfig("straumann", "Straumann"),
        ]

        self._create_fields(form, configs, section="header")

        tracking_group = QGroupBox("Seguimiento", container)
        tracking_layout = QFormLayout(tracking_group)
        tracking_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        tracking_configs = [
            FieldConfig("active", "Activar seguimiento", kind="bool", target="tracking"),
            FieldConfig("type", "Tipo", target="tracking"),
            FieldConfig("category", "Categoría", target="tracking"),
            FieldConfig("status", "Estado", target="tracking"),
            FieldConfig("ticket_number", "Número de ticket", target="tracking"),
            FieldConfig("creation_day", "Fecha de creación", target="tracking"),
            FieldConfig("case_link", "Enlace del caso", target="tracking"),
            FieldConfig("expected_arrival_date", "Fecha estimada", target="tracking"),
            FieldConfig("service_tag", "Service tag", target="tracking"),
            FieldConfig("priority", "Prioridad", kind="combo", options=PRIORITY_OPTIONS, target="tracking"),
        ]
        self._create_fields(tracking_layout, tracking_configs, section="header")
        form.addRow(tracking_group)

        return container

    def _build_call_section(self) -> QWidget:
        container = QWidget(self)
        form = QFormLayout(container)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        configs = [
            FieldConfig("request_issue", "Motivo de la solicitud", kind="multiline"),
            FieldConfig("phone_description", "Resumen de la llamada", kind="multiline"),
            FieldConfig("office_ph", "Teléfono oficina"),
            FieldConfig("direct_ph", "Teléfono directo"),
            FieldConfig("best_time", "Mejor horario"),
        ]
        self._create_fields(form, configs, section="call")
        return container

    def _build_notes_section(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

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

        configs = [
            FieldConfig("survey_link", "Enlace de encuesta"),
            FieldConfig("email_selected_template", "Plantilla de correo"),
            FieldConfig("email_tone", "Tono del correo"),
            FieldConfig("email_audience", "Audiencia del correo"),
            FieldConfig("email_custom_prompt", "Prompt personalizado", kind="multiline"),
            FieldConfig("email_last_body", "Último cuerpo generado", kind="multiline"),
            FieldConfig("email_draft", "Borrador", kind="multiline"),
            FieldConfig("email_second_line_mode", "Modo segunda línea", kind="bool"),
        ]
        self._create_fields(form, configs, section="survey")
        return container

    def _build_remote_section(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

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
        layout.addWidget(self._remote_sessions_container)

        add_button = QPushButton("Añadir sesión remota", container)
        add_button.clicked.connect(self._add_remote_session)
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        return container

    def _create_fields(self, layout: QFormLayout, configs: Iterable[FieldConfig], *, section: str) -> None:
        for config in configs:
            widget: QWidget
            if config.kind == "multiline":
                editor = QPlainTextEdit(self)
                editor.setPlaceholderText(config.placeholder or config.label)
                editor.textChanged.connect(
                    partial(self._on_multiline_changed, config.name, editor, config.target)
                )
                widget = editor
            elif config.kind == "bool":
                checkbox = QCheckBox(config.label, self)
                checkbox.toggled.connect(
                    partial(self._on_bool_changed, config.name, checkbox, config.target)
                )
                widget = checkbox
                layout.addRow(widget)
            elif config.kind == "combo":
                combo = QComboBox(self)
                combo.addItems(list(config.options or []))
                combo.currentTextChanged.connect(
                    partial(self._on_combo_changed, config.name, combo, config.target)
                )
                widget = combo
            elif config.kind == "spin":
                spin = QSpinBox(self)
                spin.setMinimum(0)
                spin.setMaximum(999)
                spin.valueChanged.connect(
                    partial(self._on_spin_changed, config.name, spin, config.target)
                )
                widget = spin
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

        for field_name, widget in self._fields.items():
            value = getattr(self._case, field_name, "") or ""
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
        self._update_remote_session_titles()

        self._syncing = False
        self._update_remote_steps_summary()
        self._toggle_hardware_visibility()
        self._update_section_states()
        self._update_hotkey_buttons()

    # ──────────────────── Case mutators ────────────────────
    def _on_text_changed(self, field_name: str, editor: QLineEdit, target: str) -> None:
        if self._syncing:
            return
        if target == "tracking":
            tracking = self._ensure_tracking()
            setattr(tracking, field_name, editor.text())
        else:
            setattr(self._case, field_name, editor.text())
        self._emit_case_changed()

    def _on_multiline_changed(self, field_name: str, editor: QPlainTextEdit, target: str) -> None:
        if self._syncing:
            return
        if target == "tracking":
            tracking = self._ensure_tracking()
            setattr(tracking, field_name, editor.toPlainText())
        else:
            setattr(self._case, field_name, editor.toPlainText())
        self._emit_case_changed()

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
        if target == "tracking":
            tracking = self._ensure_tracking()
            setattr(tracking, field_name, int(value))
        else:
            setattr(self._case, field_name, int(value))
        self._emit_case_changed()

    def _on_bool_changed(self, field_name: str, checkbox: QCheckBox, target: str, checked: bool) -> None:
        if self._syncing:
            return
        if target == "tracking":
            tracking = self._ensure_tracking()
            setattr(tracking, field_name, bool(checked))
        else:
            setattr(self._case, field_name, bool(checked))
        if field_name == "include_hardware_fields":
            self._toggle_hardware_visibility()
        self._emit_case_changed()

    def _on_hotkey_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._case.active_for_hotkeys = checked
        self.hotkeySelectionChanged.emit(checked)
        self._emit_case_changed()
        self._update_hotkey_buttons()

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
        if not self._syncing and emit_changed:
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

    def _sync_remote_sessions_from_widgets(self) -> None:
        self._case.remote_sessions = [widget.entry for widget in self._remote_session_widgets]
        self._update_remote_session_titles()
        self._update_remote_steps_summary()
        self._emit_case_changed()

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
