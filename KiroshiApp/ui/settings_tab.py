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

from KiroshiApp.core.model import CaseData


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
        self._label = QLabel("Settings tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Echo the active case identifier."""

        summary = case.case_id or case.company_name or "Sin caso seleccionado"
        self._label.setText(f"Settings tab coming soon\nCaso activo: {summary}")
