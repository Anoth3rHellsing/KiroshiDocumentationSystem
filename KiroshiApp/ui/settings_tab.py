"""Settings tab to tweak runtime configuration."""
from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.utils import load_global_config, save_global_config

LOGGER = logging.getLogger(__name__)


class SettingsTab(QWidget):
    """Expose configurable behaviour for the desktop app."""

    def __init__(
        self,
        on_autosave_changed: Callable[[bool], None] | None = None,
        on_ai_settings_changed: Callable[[dict[str, str]], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = load_global_config()
        self._on_autosave_changed = on_autosave_changed
        self._on_ai_settings_changed = on_ai_settings_changed

        self._second_line = QCheckBox("Modo 2nd Line")
        self._hardware_fields = QCheckBox("Mostrar campos de hardware")
        self._autosave_checkbox = QCheckBox("Autosave activo")
        self._ai_mode = QComboBox()
        self._ai_model = QLineEdit()
        self._ai_key = QLineEdit()
        self._ai_key.setEchoMode(QLineEdit.Password)

        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        check_layout = QVBoxLayout()
        for widget in (self._second_line, self._hardware_fields, self._autosave_checkbox):
            check_layout.addWidget(widget)
        check_container = QWidget()
        check_container.setLayout(check_layout)
        layout.addWidget(check_container)

        form_container = QWidget()
        form_layout = QFormLayout(form_container)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._ai_mode.addItems(["cloud", "local_api", "local_model"])
        form_layout.addRow(QLabel("Modo IA"), self._ai_mode)
        form_layout.addRow(QLabel("Modelo IA"), self._ai_model)
        form_layout.addRow(QLabel("API Key"), self._ai_key)
        layout.addWidget(form_container)

        button_row = QHBoxLayout()
        save_button = QPushButton("Guardar ajustes")
        save_button.clicked.connect(self._save)
        button_row.addWidget(save_button)

        update_button = QPushButton("Buscar actualizaciones")
        update_button.clicked.connect(self._check_updates)
        button_row.addWidget(update_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        for checkbox in (self._second_line, self._hardware_fields, self._autosave_checkbox):
            checkbox.stateChanged.connect(self._on_checkbox_changed)
        self._ai_mode.currentIndexChanged.connect(lambda _: self._save())
        self._ai_model.editingFinished.connect(self._save)
        self._ai_key.editingFinished.connect(self._save)

    def _load_values(self) -> None:
        self._second_line.setChecked(bool(self._config.get("mode_second_line")))
        self._hardware_fields.setChecked(bool(self._config.get("show_hardware_fields", True)))
        autosave_enabled = bool(self._config.get("autosave_enabled", True))
        self._autosave_checkbox.setChecked(autosave_enabled)
        ai_settings = self._config.get("ai", {})
        if isinstance(ai_settings, dict):
            self._ai_mode.setCurrentText(str(ai_settings.get("mode", "cloud")))
            self._ai_model.setText(str(ai_settings.get("model", "gpt-4o-mini")))
            self._ai_key.setText(str(ai_settings.get("api_key", "")))
        else:
            self._ai_mode.setCurrentText("cloud")

    def _on_checkbox_changed(self, state: int) -> None:
        self._config["mode_second_line"] = self._second_line.isChecked()
        self._config["show_hardware_fields"] = self._hardware_fields.isChecked()
        autosave_enabled = self._autosave_checkbox.isChecked()
        self._config["autosave_enabled"] = autosave_enabled
        if self._on_autosave_changed:
            self._on_autosave_changed(autosave_enabled)
        self._save()

    def _save(self) -> None:
        ai_settings = {
            "mode": self._ai_mode.currentText(),
            "model": self._ai_model.text().strip() or "gpt-4o-mini",
            "api_key": self._ai_key.text().strip(),
        }
        self._config["ai"] = ai_settings
        try:
            save_global_config(self._config)
        except Exception as exc:  # pragma: no cover
            LOGGER.error("Failed to save settings: %s", exc)
            QMessageBox.warning(self, "Ajustes", f"No se pudo guardar la configuración: {exc}")
            return
        if self._on_ai_settings_changed:
            self._on_ai_settings_changed(ai_settings)

    def _check_updates(self) -> None:
        QMessageBox.information(
            self,
            "Actualizaciones",
            "Consulta manual por actualizaciones completada. No hay paquetes nuevos.",
        )
