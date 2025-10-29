"""Settings tab implementation for the experimental desktop prototype."""
from __future__ import annotations

from collections.abc import Callable
from datetime import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
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

        self._status_label = QLabel()
        self._status_label.setObjectName("settingsStatusLabel")
        self._status_label.setWordWrap(True)

        self._reset_button = QPushButton("Restablecer predeterminados")
        self._reset_button.clicked.connect(self._reset_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Configura la experiencia del Control Tower."))
        layout.addWidget(self._second_line_checkbox)
        layout.addWidget(reminders_group)
        layout.addWidget(self._status_label)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self._reset_button)
        layout.addLayout(buttons_layout)
        layout.addStretch(1)

        self._apply_preferences_to_ui()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_reminders_config(self) -> dict[str, Any]:
        reminders = self._config.get("wellness_reminders")
        if not isinstance(reminders, dict):
            reminders = {
                "enabled": False,
                "notification_lead": 10,
                "schedule": {
                    "break_1": "10:30",
                    "lunch": "12:30",
                    "break_2": "15:00",
                },
            }
            self._config["wellness_reminders"] = reminders
        return reminders

    def _apply_preferences_to_ui(self) -> None:
        self._updating_ui = True
        try:
            second_line = bool(self._config.get("second_line_mode", False))
            self._second_line_checkbox.setChecked(second_line)

            reminders = self._get_reminders_config()
            enabled = bool(reminders.get("enabled", False))
            lead = int(reminders.get("notification_lead", 10) or 10)
            schedule = reminders.get("schedule")
            if not isinstance(schedule, dict):
                schedule = {}

            self._reminders_enabled.setChecked(enabled)
            self._lead_time.setValue(lead)

            for key, editor in self._time_fields.items():
                editor.setTime(_coerce_time(schedule.get(key, "10:30")))
                editor.setEnabled(enabled)

            self._lead_time.setEnabled(enabled)
            self._status_label.setText(self._build_status_text(second_line, enabled))
        finally:
            self._updating_ui = False

    def _build_status_text(self, second_line: bool, reminders_enabled: bool) -> str:
        summary = []
        summary.append(
            "Modo 2nd Line activado." if second_line else "Modo 2nd Line desactivado."
        )
        if reminders_enabled:
            summary.append(
                "Recordatorios habilitados — recibirás avisos antes de cada checkpoint."
            )
        else:
            summary.append("Los recordatorios están desactivados.")
        return "\n".join(summary)

    def _persist_preferences(self) -> None:
        if self._save_config:
            self._save_config(self._config, base_path=self._base_path)
        if self._on_preferences_changed:
            self._on_preferences_changed(dict(self._config))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _handle_second_line_changed(self, state: int) -> None:
        if self._updating_ui:
            return
        self._config["second_line_mode"] = state == Qt.Checked
        reminders = self._get_reminders_config()
        self._status_label.setText(
            self._build_status_text(self._config["second_line_mode"], reminders.get("enabled", False))
        )
        self._persist_preferences()

    def _handle_reminders_changed(self) -> None:
        if self._updating_ui:
            return
        reminders = self._get_reminders_config()
        enabled = self._reminders_enabled.isChecked()
        reminders["enabled"] = enabled
        reminders["notification_lead"] = int(self._lead_time.value())

        schedule = reminders.setdefault("schedule", {})
        for key, editor in self._time_fields.items():
            schedule[key] = editor.time().toString("HH:mm")
            editor.setEnabled(enabled)

        self._lead_time.setEnabled(enabled)
        self._status_label.setText(
            self._build_status_text(self._config.get("second_line_mode", False), enabled)
        )
        self._persist_preferences()

    def _reset_defaults(self) -> None:
        self._config["second_line_mode"] = False
        self._config["wellness_reminders"] = {
            "enabled": False,
            "notification_lead": 10,
            "schedule": {
                "break_1": "10:30",
                "lunch": "12:30",
                "break_2": "15:00",
            },
        }
        self._apply_preferences_to_ui()
        self._persist_preferences()

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    def update_preferences(self, config: dict[str, Any]) -> None:
        """Update the form with freshly persisted settings."""

        self._config.update(config)
        self._apply_preferences_to_ui()
