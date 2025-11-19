"""Case tab form for the experimental desktop prototype."""
from __future__ import annotations

from functools import partial
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.model import (
    PRIORITY_OPTIONS,
    CaseData,
    RemoteSessionEntry,
    TrackingData,
)


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
        self.title_edit.setPlaceholderText("Session title")
        self.title_edit.setText(entry.title)
        self.title_edit.textChanged.connect(self._on_changed)
        header_layout.addWidget(QLabel("Title:", self))
        header_layout.addWidget(self.title_edit)

        remove_button = QPushButton("Remove", self)
        remove_button.clicked.connect(lambda: self.removed.emit(self.entry.session_id))
        header_layout.addWidget(remove_button)

        layout.addLayout(header_layout)

        self.notes_edit = QPlainTextEdit(self)
        self.notes_edit.setPlaceholderText("Session notes")
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

        self._header_fields: dict[str, QWidget] = {}
        self._call_fields: dict[str, QWidget] = {}
        self._internal_fields: dict[str, QWidget] = {}
        self._conclusion_fields: dict[str, QWidget] = {}
        self._survey_fields: dict[str, QWidget] = {}
        self._tracking_fields: dict[str, QWidget] = {}
        self._hardware_fields: dict[str, QWidget] = {}
        self._hardware_table_rows: dict[str, tuple[QTableWidget, int]] = {}
        self._remote_session_widgets: List[RemoteSessionWidget] = []

        self._build_ui()
        self._populate_from_case()

    # ──────────────────── UI builders ────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(QLabel("Case overview", self))
        header.addStretch(1)
        self._hotkey_checkbox = QCheckBox("Use this case for global clipboard hotkeys", self)
        self._hotkey_checkbox.toggled.connect(self._on_hotkey_toggled)
        if not self._hotkeys_available:
            label_suffix = " (no disponible)"
            self._hotkey_checkbox.setText(
                f"Use this case for global clipboard hotkeys{label_suffix}"
            )
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

        container_layout.addWidget(self._build_header_section())
        container_layout.addWidget(self._build_call_section())
        container_layout.addWidget(self._build_internal_notes_section())
        container_layout.addWidget(self._build_conclusion_section())
        container_layout.addWidget(self._build_survey_section())
        container_layout.addWidget(self._build_remote_sessions_section())
        container_layout.addWidget(self._build_tracking_section())
        container_layout.addWidget(self._build_hardware_section())
        container_layout.addStretch(1)

    def _build_header_section(self) -> QWidget:
        group = QGroupBox("Cabecera", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        header_fields: list[tuple[str, str, bool]] = [
            ("company_name", "Company name", False),
            ("case_id", "Case ID", False),
            ("subscription_id", "Subscription ID", False),
            ("application_version", "Application version", False),
            ("brief_description", "Brief description", True),
            ("description", "Full description", True),
            ("dongle_number", "Dongle number", False),
            ("email", "Email", False),
            ("teamviewer_id", "TeamViewer ID", False),
            ("teamviewer_password", "TeamViewer password", False),
        ]

        for field_name, label, multiline in header_fields:
            widget: QWidget
            if multiline:
                editor = QPlainTextEdit(group)
                editor.textChanged.connect(partial(self._on_multiline_changed, field_name, editor))
                widget = editor
            else:
                editor = QLineEdit(group)
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._header_fields[field_name] = widget
            form.addRow(label + ":", widget)

        return group

    def _build_call_section(self) -> QWidget:
        group = QGroupBox("Llamada", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        call_fields: list[tuple[str, str, bool]] = [
            ("caller_name", "Caller name", False),
            ("phone_number", "Phone number", False),
            ("phone_description", "Phone description", True),
            ("request_issue", "Reported issue", True),
            ("contact_name", "Contact name", False),
            ("office_ph", "Office phone", False),
            ("direct_ph", "Direct phone", False),
            ("best_time", "Best time", False),
        ]

        for field_name, label, multiline in call_fields:
            widget: QWidget
            if multiline:
                editor = QPlainTextEdit(group)
                editor.textChanged.connect(partial(self._on_multiline_changed, field_name, editor))
                widget = editor
            else:
                editor = QLineEdit(group)
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._call_fields[field_name] = widget
            form.addRow(label + ":", widget)

        return group

    def _build_internal_notes_section(self) -> QWidget:
        group = QGroupBox("Notas internas", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        internal_fields: list[tuple[str, str, bool]] = [
            ("internal_helpjuice", "Internal Helpjuice", True),
            ("internal_logs", "Internal logs", True),
            ("additional_info", "Additional info", True),
            ("third_line_hj_article", "3rd line HJ article", False),
            ("third_line_troubleshoot_summary", "3rd line troubleshoot summary", True),
            ("third_line_comments", "3rd line comments", True),
            ("third_line_reseller_name", "Reseller name", False),
            ("third_line_reseller_phone", "Reseller phone", False),
            ("third_line_reseller_phone_alt", "Reseller phone (alt)", False),
            ("third_line_reseller_email", "Reseller email", False),
            ("third_line_clinic_rep_name", "Clinic rep name", False),
            ("third_line_clinic_rep_phone", "Clinic rep phone", False),
            ("third_line_clinic_rep_phone_alt", "Clinic rep phone (alt)", False),
            ("third_line_tv_id", "3rd line TV ID", False),
            ("third_line_tv_password", "3rd line TV password", False),
            ("third_line_unite_pin", "3rd line Unite PIN", False),
        ]

        for field_name, label, multiline in internal_fields:
            widget: QWidget
            if multiline:
                editor = QPlainTextEdit(group)
                editor.textChanged.connect(partial(self._on_multiline_changed, field_name, editor))
                widget = editor
            else:
                editor = QLineEdit(group)
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._internal_fields[field_name] = widget
            form.addRow(label + ":", widget)

        return group

    def _build_conclusion_section(self) -> QWidget:
        group = QGroupBox("Conclusión", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        conclusion_fields: list[tuple[str, str, bool]] = [
            ("solution", "Solution", True),
            ("root_cause", "Root cause", True),
            ("repro_steps", "Repro steps", True),
        ]

        for field_name, label, multiline in conclusion_fields:
            widget: QWidget
            editor = QPlainTextEdit(group) if multiline else QLineEdit(group)
            if isinstance(editor, QPlainTextEdit):
                editor.textChanged.connect(partial(self._on_multiline_changed, field_name, editor))
            else:
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
            widget = editor
            self._conclusion_fields[field_name] = widget
            form.addRow(label + ":", widget)

        return group

    def _build_survey_section(self) -> QWidget:
        group = QGroupBox("Encuesta", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        survey_fields: list[tuple[str, str, bool]] = [
            ("survey_link", "Survey link", False),
            ("patterson", "Patterson", False),
            ("straumann", "Straumann", False),
            ("esc_name", "ESC name", False),
            ("esc_ph", "ESC phone", False),
            ("esc_email", "ESC email", False),
        ]

        for field_name, label, multiline in survey_fields:
            widget: QWidget
            if multiline:
                editor = QPlainTextEdit(group)
                editor.textChanged.connect(partial(self._on_multiline_changed, field_name, editor))
                widget = editor
            else:
                editor = QLineEdit(group)
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._survey_fields[field_name] = widget
            form.addRow(label + ":", widget)

        return group

    def _build_tracking_section(self) -> QWidget:
        group = QGroupBox("Progress tracking", self)
        layout = QVBoxLayout(group)

        self._tracking_active_checkbox = QCheckBox("Track this case", group)
        self._tracking_active_checkbox.toggled.connect(self._on_tracking_active_toggled)
        layout.addWidget(self._tracking_active_checkbox)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        layout.addLayout(form)

        text_fields = [
            ("type", "Type"),
            ("category", "Category"),
            ("status", "Status"),
            ("ticket_number", "Ticket number"),
            ("creation_day", "Creation day"),
            ("case_link", "Case link"),
            ("expected_arrival_date", "Expected arrival"),
            ("service_tag", "Service tag"),
        ]

        for field_name, label in text_fields:
            editor = QLineEdit(group)
            editor.textChanged.connect(partial(self._on_tracking_text_changed, field_name, editor))
            self._tracking_fields[field_name] = editor
            form.addRow(label + ":", editor)

        self._priority_combo = QComboBox(group)
        self._priority_combo.addItems(PRIORITY_OPTIONS)
        self._priority_combo.currentTextChanged.connect(self._on_priority_changed)
        form.addRow("Priority:", self._priority_combo)

        return group

    def _build_remote_sessions_section(self) -> QWidget:
        group = QGroupBox("Sesiones remotas", self)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self._remote_sessions_container = QWidget(group)
        self._remote_sessions_layout = QVBoxLayout(self._remote_sessions_container)
        self._remote_sessions_layout.setContentsMargins(0, 0, 0, 0)
        self._remote_sessions_layout.setSpacing(8)
        layout.addWidget(self._remote_sessions_container)

        add_button = QPushButton("Add remote session", group)
        add_button.clicked.connect(self._add_remote_session)
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)

        return group

    def _build_hardware_section(self) -> QWidget:
        group = QGroupBox("Hardware diagnostics", self)
        layout = QVBoxLayout(group)

        self._include_hardware_checkbox = QCheckBox("Include hardware issue fields", group)
        self._include_hardware_checkbox.setToolTip(
            "Muestra u oculta los datos de hardware cuando sean relevantes para el caso."
        )
        self._include_hardware_checkbox.toggled.connect(self._on_include_hardware_toggled)
        layout.addWidget(self._include_hardware_checkbox)

        self._hardware_fields_container = QWidget(group)
        hardware_layout = QVBoxLayout(self._hardware_fields_container)
        hardware_layout.setContentsMargins(0, 0, 0, 0)
        hardware_layout.setSpacing(12)

        pc_fields: list[tuple[str, str, str, bool, str]] = [
            (
                "hardware_test",
                "Hardware test",
                "multiline",
                False,
                "Resumen de pruebas realizadas y resultados en el PC.",
            ),
            (
                "service_tag",
                "Dell service tag",
                "text",
                True,
                "Etiqueta necesaria para reclamaciones y soporte de Dell.",
            ),
            ("pc_model", "PC model", "text", False, "Modelo exacto del PC en revisión."),
            ("windows_version", "Windows version", "text", False, "Versión y build instaladas."),
            ("bios_version", "BIOS version", "text", False, "Versión de BIOS/UEFI."),
            ("graphics_card", "Graphics card", "text", False, "Modelo de GPU presente."),
            ("processor", "Processor", "text", False, "Modelo de CPU."),
            ("warranty", "Warranty", "text", False, "Cobertura y fecha de garantía."),
            (
                "dongle_deployment_date",
                "Dongle deployment date",
                "text",
                False,
                "Fecha aproximada de activación del dongle.",
            ),
            (
                "dell_issue_start_date",
                "Issue start date",
                "text",
                False,
                "Cuándo comenzaron los síntomas en el PC.",
            ),
            (
                "dell_command_updates_status",
                "Command Updates status",
                "text",
                False,
                "Estado de Dell Command/Updates y parches aplicados.",
            ),
            (
                "dell_power_options_setup",
                "Power options setup",
                "text",
                False,
                "Perfil de energía configurado (alto rendimiento, etc.).",
            ),
            (
                "dell_optimizer_setup",
                "Optimizer setup",
                "text",
                False,
                "Ajustes o perfiles aplicados en Dell Optimizer.",
            ),
            (
                "dell_intel_ppm_installed",
                "Intel PPM installed",
                "text",
                False,
                "Estado del controlador Intel PPM o parches relacionados.",
            ),
            (
                "dell_cpu_speed_or_throttling",
                "CPU speed/throttling",
                "text",
                False,
                "Velocidad observada y si hubo estrangulamiento.",
            ),
            (
                "dell_gpu_usage_integrated",
                "GPU usage (integrated)",
                "text",
                False,
                "Consumo o carga de la GPU integrada.",
            ),
            (
                "dell_gpu_usage_dedicated",
                "GPU usage (dedicated)",
                "text",
                False,
                "Consumo o carga de la GPU dedicada.",
            ),
            (
                "dell_cpu_utilization",
                "CPU utilisation",
                "text",
                False,
                "Promedio y picos de uso de CPU durante las pruebas.",
            ),
            (
                "dell_benchmark_results",
                "Benchmark results",
                "multiline",
                False,
                "Resultados relevantes de benchmarks o pruebas de estrés.",
            ),
            (
                "dell_ultra_resolution_support",
                "Ultra resolution support",
                "text",
                False,
                "Compatibilidad con resoluciones ultra o 4K.",
            ),
            (
                "dell_gpu_driver_versions",
                "GPU driver versions",
                "text",
                False,
                "Versiones de drivers instaladas (Intel/NVIDIA/AMD).",
            ),
            (
                "dell_reliability_monitor_results",
                "Reliability monitor",
                "multiline",
                False,
                "Eventos destacados del monitor de confiabilidad.",
            ),
            (
                "dell_diagnostics_results",
                "Diagnostics results",
                "multiline",
                False,
                "Resultados de ePSA u otras pruebas de diagnóstico.",
            ),
            (
                "dell_windows_reimaged",
                "Windows reimaged",
                "text",
                False,
                "Indicar si Windows fue reinstalado o reimaginado.",
            ),
        ]

        scanner_fields: list[tuple[str, str, str, bool, str]] = [
            (
                "scanner_sn",
                "Scanner S/N",
                "text",
                True,
                "Número de serie del escáner; imprescindible para reemplazos.",
            ),
            (
                "base_sn",
                "Base S/N",
                "text",
                True,
                "Número de serie de la base o cradle del escáner.",
            ),
            (
                "trios_module_version",
                "TRIOS module version",
                "text",
                False,
                "Versión del módulo TRIOS instalado.",
            ),
            (
                "scanner_previous_replacements",
                "Scanner replacements",
                "spin",
                False,
                "Cantidad de reemplazos previos registrados.",
            ),
            (
                "scanner_accidental_damage",
                "Scanner accidental damage",
                "text",
                False,
                "Notas sobre daño accidental reportado.",
            ),
            (
                "clinic_name",
                "Clinic name",
                "text",
                False,
                "Nombre comercial de la clínica involucrada.",
            ),
            (
                "clinic_contact_name",
                "Clinic contact name",
                "text",
                False,
                "Persona de contacto principal.",
            ),
            (
                "clinic_contact_phone",
                "Clinic contact phone",
                "text",
                False,
                "Teléfono directo del contacto.",
            ),
            (
                "clinic_contact_email",
                "Clinic contact email",
                "text",
                False,
                "Correo del contacto; útil para envíos RMA.",
            ),
            (
                "clinic_address_line_1",
                "Clinic address line 1",
                "text",
                False,
                "Dirección principal para envíos.",
            ),
            (
                "clinic_address_line_2",
                "Clinic address line 2",
                "text",
                False,
                "Complemento de dirección (suite, piso).",
            ),
            ("clinic_city", "Clinic city", "text", False, "Ciudad de la clínica."),
            ("clinic_state", "Clinic state", "text", False, "Estado o provincia."),
            (
                "clinic_postal_code",
                "Clinic postal code",
                "text",
                False,
                "Código postal verificado para envíos.",
            ),
            (
                "customer_trios_only",
                "Customer TRIOS only",
                "checkbox",
                False,
                "Marca si el cliente solo utiliza TRIOS sin otras unidades.",
            ),
            (
                "support_fee_accepted",
                "Support fee accepted",
                "checkbox",
                False,
                "Confirma si se aprobó la tarifa de soporte.",
            ),
        ]

        hardware_layout.addWidget(
            self._build_hardware_group(
                "PC Hardware", pc_fields, self._hardware_fields_container
            )
        )
        hardware_layout.addWidget(
            self._build_hardware_group(
                "Scanner Hardware", scanner_fields, self._hardware_fields_container
            )
        )

        layout.addWidget(self._hardware_fields_container)
        return group

    def _build_hardware_group(
        self,
        title: str,
        fields: list[tuple[str, str, str, bool, str]],
        parent: QWidget,
    ) -> QWidget:
        group = QGroupBox(title, parent)
        group.setCheckable(False)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        table = QTableWidget(len(fields), 2, group)
        table.setHorizontalHeaderLabels(["Campo", "Valor"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setToolTip("Vista rápida de campos de hardware en modo solo lectura.")

        for row, (field_name, label, _kind, _critical, tooltip) in enumerate(fields):
            label_item = QTableWidgetItem(label)
            label_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            label_item.setToolTip(tooltip)
            value_item = QTableWidgetItem("")
            value_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            value_item.setToolTip(tooltip)
            table.setItem(row, 0, label_item)
            table.setItem(row, 1, value_item)
            self._hardware_table_rows[field_name] = (table, row)

        layout.addWidget(table)

        controls = QHBoxLayout()
        controls.addStretch(1)
        copy_button = QPushButton("Copiar tabla", group)
        copy_button.setToolTip("Copia la tabla en formato TSV al portapapeles.")
        copy_button.clicked.connect(lambda: self._copy_hardware_table(table))
        controls.addWidget(copy_button)
        layout.addLayout(controls)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for field_name, label, kind, _critical, tooltip in fields:
            widget: QWidget
            if kind == "multiline":
                editor = QPlainTextEdit(group)
                editor.setToolTip(tooltip)
                editor.textChanged.connect(
                    partial(self._on_hardware_multiline_changed, field_name, editor)
                )
                widget = editor
            elif kind == "spin":
                spin = QSpinBox(group)
                spin.setMinimum(0)
                spin.setMaximum(999)
                spin.setToolTip(tooltip)
                spin.valueChanged.connect(
                    partial(self._on_hardware_spin_changed, field_name, spin)
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
                editor = QLineEdit(group)
                editor.setToolTip(tooltip)
                editor.textChanged.connect(
                    partial(self._on_hardware_text_changed, field_name, editor)
                )
                widget = editor
            self._hardware_fields[field_name] = widget
            form.addRow(label + ":", widget)

        layout.addLayout(form)
        return group

    # ──────────────────── Population helpers ────────────────────
    def _populate_from_case(self) -> None:
        self._syncing = True

        for field_name, widget in (
            list(self._header_fields.items())
            + list(self._call_fields.items())
            + list(self._internal_fields.items())
            + list(self._conclusion_fields.items())
            + list(self._survey_fields.items())
        ):
            value = getattr(self._case, field_name, "") or ""
            if isinstance(widget, QLineEdit):
                widget.setText(value)
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText(value)

        tracking = self._case.tracking if isinstance(self._case.tracking, TrackingData) else TrackingData()
        self._tracking_active_checkbox.setChecked(bool(tracking.active))
        for field_name, widget in self._tracking_fields.items():
            value = getattr(tracking, field_name, "") or ""
            if isinstance(widget, QLineEdit):
                widget.setText(value)
        current_priority = tracking.priority or PRIORITY_OPTIONS[0]
        index = max(0, self._priority_combo.findText(current_priority))
        self._priority_combo.setCurrentIndex(index)

        self._hotkey_checkbox.setChecked(bool(self._case.active_for_hotkeys))
        self._include_hardware_checkbox.setChecked(bool(self._case.include_hardware_fields))
        self._hardware_fields_container.setVisible(self._case.include_hardware_fields)

        for field_name, widget in self._hardware_fields.items():
            value = getattr(self._case, field_name, "")
            if isinstance(widget, QLineEdit):
                widget.setText(str(value) if value is not None else "")
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText(str(value) if value is not None else "")
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(value))
                except (TypeError, ValueError):
                    widget.setValue(0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))

        self._refresh_hardware_tables()

        self._clear_remote_session_widgets()
        sessions = list(self._case.remote_sessions or [])
        if sessions:
            for entry in sessions:
                self._add_remote_session(entry, emit_changed=False)
        else:
            self._add_remote_session(RemoteSessionEntry(), emit_changed=False)
        self._update_remote_session_titles()

        self._syncing = False

    # ──────────────────── Case mutators ────────────────────
    def _on_text_changed(self, field_name: str, editor: QLineEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.text())
        self._emit_case_changed()

    def _on_multiline_changed(self, field_name: str, editor: QPlainTextEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.toPlainText())
        self._emit_case_changed()

    def _on_tracking_active_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        tracking = self._ensure_tracking()
        tracking.active = checked
        self._emit_case_changed()

    def _on_tracking_text_changed(self, field_name: str, editor: QLineEdit) -> None:
        if self._syncing:
            return
        tracking = self._ensure_tracking()
        setattr(tracking, field_name, editor.text())
        self._emit_case_changed()

    def _on_priority_changed(self, value: str) -> None:
        if self._syncing:
            return
        tracking = self._ensure_tracking()
        tracking.priority = value
        self._emit_case_changed()

    def _on_hotkey_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._case.active_for_hotkeys = checked
        self.hotkeySelectionChanged.emit(checked)
        self._emit_case_changed()

    def _on_include_hardware_toggled(self, checked: bool) -> None:
        if self._syncing:
            return
        self._case.include_hardware_fields = checked
        self._hardware_fields_container.setVisible(checked)
        self._emit_case_changed()

    def _on_hardware_text_changed(self, field_name: str, editor: QLineEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.text())
        self._update_hardware_table_field(field_name, editor.text())
        self._emit_case_changed()

    def _on_hardware_multiline_changed(self, field_name: str, editor: QPlainTextEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.toPlainText())
        self._update_hardware_table_field(field_name, editor.toPlainText())
        self._emit_case_changed()

    def _on_hardware_spin_changed(self, field_name: str, spin: QSpinBox, value: int) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, int(value))
        self._update_hardware_table_field(field_name, value)
        self._emit_case_changed()

    def _on_hardware_checkbox_toggled(self, field_name: str, checkbox: QCheckBox) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, bool(checkbox.isChecked()))
        self._update_hardware_table_field(field_name, checkbox.isChecked())
        self._emit_case_changed()

    def _copy_hardware_table(self, table: QTableWidget) -> None:
        rows: list[str] = []
        for row in range(table.rowCount()):
            label = table.item(row, 0).text() if table.item(row, 0) else ""
            value = table.item(row, 1).text() if table.item(row, 1) else ""
            rows.append(f"{label}\t{value}")
        QGuiApplication.clipboard().setText("\n".join(rows))

    def _refresh_hardware_tables(self) -> None:
        for field_name in self._hardware_table_rows:
            value = getattr(self._case, field_name, "")
            self._update_hardware_table_field(field_name, value)

    def _update_hardware_table_field(self, field_name: str, value: object) -> None:
        if field_name not in self._hardware_table_rows:
            return
        table, row = self._hardware_table_rows[field_name]
        display_value = self._normalize_hardware_value(value)
        item = table.item(row, 1)
        if item is None:
            item = QTableWidgetItem()
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 1, item)
        item.setText(display_value)

        critical_fields = {"scanner_sn", "base_sn", "service_tag"}
        if field_name in critical_fields and not display_value:
            item.setBackground(table.palette().alternateBase())
            item.setToolTip("Falta un campo crítico: completa este dato antes de cerrar el caso.")
        else:
            item.setBackground(table.palette().base())
            item.setToolTip(table.item(row, 0).toolTip())

    def _normalize_hardware_value(self, value: object) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if value is None:
            return ""
        return str(value).strip()

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
        self.caseChanged.emit(self._case)


__all__ = ["CaseTab"]
