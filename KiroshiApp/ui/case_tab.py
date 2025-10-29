"""Case tab form for the experimental desktop prototype."""
from __future__ import annotations

from functools import partial
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
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

    def __init__(self, case: CaseData | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._case = case or CaseData()
        self._syncing = False

        self._client_fields: dict[str, QWidget] = {}
        self._tracking_fields: dict[str, QWidget] = {}
        self._hardware_fields: dict[str, QWidget] = {}
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

        container_layout.addWidget(self._build_client_section())
        container_layout.addWidget(self._build_tracking_section())
        container_layout.addWidget(self._build_remote_sessions_section())
        container_layout.addWidget(self._build_hardware_section())
        container_layout.addStretch(1)

    def _build_client_section(self) -> QWidget:
        group = QGroupBox("Client information", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        client_fields: list[tuple[str, str, bool]] = [
            ("company_name", "Company name", False),
            ("case_id", "Case ID", False),
            ("subscription_id", "Subscription ID", False),
            ("application_version", "Application version", False),
            ("brief_description", "Brief description", True),
            ("description", "Full description", True),
            ("caller_name", "Caller name", False),
            ("phone_number", "Phone number", False),
            ("phone_description", "Phone description", True),
            ("dongle_number", "Dongle number", False),
            ("teamviewer_id", "TeamViewer ID", False),
            ("teamviewer_password", "TeamViewer password", False),
            ("email", "Email", False),
            ("internal_helpjuice", "Internal Helpjuice", False),
            ("internal_logs", "Internal logs", True),
            ("additional_info", "Additional info", True),
            ("solution", "Solution", True),
        ]

        for field_name, label, multiline in client_fields:
            widget: QWidget
            if multiline:
                editor = QPlainTextEdit(group)
                editor.textChanged.connect(partial(self._on_multiline_changed, field_name, editor))
                widget = editor
            else:
                editor = QLineEdit(group)
                editor.textChanged.connect(partial(self._on_text_changed, field_name, editor))
                widget = editor
            self._client_fields[field_name] = widget
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
        group = QGroupBox("Remote sessions", self)
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
                spin.valueChanged.connect(partial(self._on_hardware_spin_changed, field_name, spin))
                widget = spin
            else:
                editor = QLineEdit(self._hardware_fields_container)
                editor.textChanged.connect(partial(self._on_hardware_text_changed, field_name, editor))
                widget = editor
            self._hardware_fields[field_name] = widget
            hardware_form.addRow(label + ":", widget)

        self._customer_trios_only = QCheckBox("Customer TRIOS only", self._hardware_fields_container)
        self._customer_trios_only.toggled.connect(
            lambda checked: self._set_case_flag("customer_trios_only", checked)
        )
        hardware_form.addRow(self._customer_trios_only)

        self._support_fee_accepted = QCheckBox("Support fee accepted", self._hardware_fields_container)
        self._support_fee_accepted.toggled.connect(
            lambda checked: self._set_case_flag("support_fee_accepted", checked)
        )
        hardware_form.addRow(self._support_fee_accepted)

        layout.addWidget(self._hardware_fields_container)
        return group

    # ──────────────────── Population helpers ────────────────────
    def _populate_from_case(self) -> None:
        self._syncing = True

        for field_name, widget in self._client_fields.items():
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

        self._customer_trios_only.setChecked(bool(self._case.customer_trios_only))
        self._support_fee_accepted.setChecked(bool(self._case.support_fee_accepted))

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
        self._emit_case_changed()

    def _on_hardware_multiline_changed(self, field_name: str, editor: QPlainTextEdit) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, editor.toPlainText())
        self._emit_case_changed()

    def _on_hardware_spin_changed(self, field_name: str, spin: QSpinBox, value: int) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, int(value))
        self._emit_case_changed()

    def _set_case_flag(self, field_name: str, value: bool) -> None:
        if self._syncing:
            return
        setattr(self._case, field_name, bool(value))
        self._emit_case_changed()

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
