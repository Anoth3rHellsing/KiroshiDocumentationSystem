"""Settings tab implementation for the experimental desktop prototype."""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


def _coerce_time(value: object) -> time:
    """Return a :class:`datetime.time` instance from persisted settings values."""

    if isinstance(value, time):
        return value
    if isinstance(value, str) and value:
        parts = value.split(":")
        if len(parts) >= 2:
            hour, minute = parts[:2]
            try:
                return time(int(hour), int(minute))
            except ValueError:
                pass
    return time(10, 30)

from KiroshiApp.core.model import CaseData


DEFAULT_CONFIG: dict[str, Any] = {
    "second_line_mode": False,
    "reminders": {
        "enabled": False,
        "lead_time_minutes": 15,
        "break_1": "10:30",
        "lunch": "13:00",
        "break_2": "16:00",
    },
}


class SettingsTab(QWidget):
    """Interactive form that persists workspace preferences to disk."""

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        base_path: Path | str | None = None,
        load_config: Callable[..., dict[str, Any]] | None = None,
        save_config: Callable[..., object] | None = None,
        on_preferences_changed: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__()
        self._base_path = base_path
        self._load_config = load_config
        self._save_config = save_config
        self._on_preferences_changed = on_preferences_changed
        loaded = load_config(base_path=base_path) if load_config else {}
        self._config: dict[str, Any] = dict(loaded)
        if config:
            self._config.update(config)
        self._config.setdefault("second_line_mode", DEFAULT_CONFIG["second_line_mode"])
        reminders_config = self._config.get("reminders")
        if not isinstance(reminders_config, dict):
            reminders_config = {}
        merged_reminders = dict(DEFAULT_CONFIG["reminders"])
        merged_reminders.update(reminders_config)
        self._config["reminders"] = merged_reminders
        self._updating_ui = False

        self._second_line_checkbox = QCheckBox("Activar modo 2nd Line")
        self._second_line_checkbox.stateChanged.connect(self._handle_second_line_changed)

        reminders_group = QGroupBox("Recordatorios de seguimiento")
        reminders_layout = QFormLayout(reminders_group)
        reminders_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._reminders_enabled = QCheckBox("Habilitar recordatorios")
        self._reminders_enabled.stateChanged.connect(self._handle_reminders_changed)

        self._lead_time = QSpinBox()
        self._lead_time.setRange(1, 240)
        self._lead_time.setSuffix(" min")
        self._lead_time.valueChanged.connect(self._handle_reminders_changed)

        self._time_fields: dict[str, QTimeEdit] = {}
        for key, label in (
            ("break_1", "Pausa mañana"),
            ("lunch", "Almuerzo"),
            ("break_2", "Pausa tarde"),
        ):
            editor = QTimeEdit()
            editor.setDisplayFormat("HH:mm")
            editor.timeChanged.connect(self._handle_reminders_changed)
            reminders_layout.addRow(label, editor)
            self._time_fields[key] = editor

        reminders_layout.insertRow(0, QLabel("Habilitar"), self._reminders_enabled)
        reminders_layout.insertRow(1, QLabel("Avisar con"), self._lead_time)

        self._status_message = "Las preferencias se guardan automáticamente en este equipo."
        self._status_label = QLabel()
        self._status_label.setObjectName("settingsStatusLabel")
        self._status_label.setWordWrap(True)

        self._reset_button = QPushButton("Restablecer predeterminados")
        self._reset_button.clicked.connect(self._reset_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(self._second_line_checkbox)
        layout.addWidget(reminders_group)
        layout.addWidget(self._status_label)
        layout.addWidget(self._reset_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

        self._sync_from_config()
        self._status_label.setText(
            f"{self._status_message}\nCaso activo: Sin caso seleccionado"
        )

    def refresh_case(self, case: CaseData) -> None:
        """Echo the active case identifier."""

        summary = case.case_id or case.company_name or "Sin caso seleccionado"
        self._status_label.setText(f"{self._status_message}\nCaso activo: {summary}")

    def _sync_from_config(self) -> None:
        """Synchronise widgets with the current configuration values."""

        self._updating_ui = True
        try:
            second_line_enabled = bool(self._config.get("second_line_mode", False))
            self._second_line_checkbox.setChecked(second_line_enabled)

            reminders_value = self._config.get("reminders", {})
            reminders_config = reminders_value if isinstance(reminders_value, dict) else {}
            enabled = bool(reminders_config.get("enabled", False))
            default_lead_time = DEFAULT_CONFIG["reminders"]["lead_time_minutes"]
            try:
                lead_time = int(reminders_config.get("lead_time_minutes", default_lead_time))
            except (TypeError, ValueError):
                lead_time = default_lead_time
            lead_time = max(self._lead_time.minimum(), min(self._lead_time.maximum(), lead_time))
            self._lead_time.setValue(lead_time)
            for key, field in self._time_fields.items():
                reminder_time = _coerce_time(reminders_config.get(key))
                field.setTime(QTime(reminder_time.hour, reminder_time.minute))

            self._reminders_enabled.setChecked(enabled)
            self._apply_reminders_enabled_state(enabled)
        finally:
            self._updating_ui = False

    def _apply_reminders_enabled_state(self, enabled: bool) -> None:
        self._lead_time.setEnabled(enabled)
        for field in self._time_fields.values():
            field.setEnabled(enabled)

    def _persist_config(self) -> None:
        if self._save_config:
            self._save_config(self._config, base_path=self._base_path)
        if self._on_preferences_changed:
            self._on_preferences_changed(deepcopy(self._config))

    def _handle_second_line_changed(self, state: int) -> None:
        if self._updating_ui:
            return
        enabled = state == Qt.CheckState.Checked
        self._config["second_line_mode"] = enabled
        self._persist_config()

    def _handle_reminders_changed(self, *_: object) -> None:
        if self._updating_ui:
            return

        enabled = self._reminders_enabled.isChecked()
        self._apply_reminders_enabled_state(enabled)
        reminders_config: dict[str, Any] = {
            "enabled": enabled,
            "lead_time_minutes": int(self._lead_time.value()),
        }
        for key, field in self._time_fields.items():
            time_value = field.time()
            reminders_config[key] = f"{time_value.hour():02d}:{time_value.minute():02d}"
        self._config["reminders"] = reminders_config
        self._persist_config()

    def _reset_defaults(self, *_: object) -> None:
        self._config = deepcopy(DEFAULT_CONFIG)
        self._sync_from_config()
        self._persist_config()
