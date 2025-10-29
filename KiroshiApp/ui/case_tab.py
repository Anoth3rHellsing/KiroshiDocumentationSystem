"""Case tab UI components."""
from __future__ import annotations

import logging
from functools import partial
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.model import CaseData
from ..core.storage import save_autosave

LOGGER = logging.getLogger(__name__)


class CaseTab(QWidget):
    """Editable form bound to a :class:`~KiroshiApp.core.model.CaseData`."""

    AUTOSAVE_DEBOUNCE_MS = 750

    def __init__(self, case: CaseData | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.case = case or CaseData()
        self._autosave_enabled = True
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._perform_autosave)

        self._field_widgets: dict[str, QWidget] = {}
        self._category_bars: dict[str, QProgressBar] = {}

        self._categories = {
            "Identificación": ["case_id", "company_name", "subscription_id"],
            "Contacto": ["caller_name", "email", "phone_number"],
            "Resolución": ["brief_description", "description", "solution", "additional_info"],
        }

        self._build_ui()
        self._populate_from_case()

    # ------------------------------------------------------------------ UI setup
    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(12)

        overall_layout = QHBoxLayout()
        overall_layout.setContentsMargins(0, 0, 0, 0)
        overall_layout.setSpacing(8)

        self._overall_progress = QProgressBar()
        self._overall_progress.setRange(0, 100)
        self._overall_progress.setFormat("Progreso general: %p%")
        overall_layout.addWidget(self._overall_progress, 1)

        self._autosave_toggle = QCheckBox("Autosave activado")
        self._autosave_toggle.setChecked(True)
        self._autosave_toggle.stateChanged.connect(self._toggle_autosave)
        overall_layout.addWidget(self._autosave_toggle)
        outer_layout.addLayout(overall_layout)

        self._category_container = QWidget()
        category_layout = QVBoxLayout(self._category_container)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(6)
        for category in self._categories:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setFormat(f"{category}: %p%")
            self._category_bars[category] = bar
            category_layout.addWidget(bar)
        outer_layout.addWidget(self._category_container)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        form_container = QWidget()
        self._form_layout = QFormLayout(form_container)
        self._form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll_area.setWidget(form_container)
        outer_layout.addWidget(scroll_area, 1)

        # Basic information fields
        self._add_line_edit("company_name", "Compañía")
        self._add_line_edit("subscription_id", "Subscription ID")
        self._add_line_edit("brief_description", "Resumen breve", multiline=True)
        self._add_line_edit("case_id", "Case ID")
        self._add_line_edit("caller_name", "Contacto principal")
        self._add_line_edit("email", "Email")
        self._add_line_edit("phone_number", "Teléfono")
        self._add_line_edit("description", "Descripción", multiline=True)
        self._add_line_edit("solution", "Solución", multiline=True)
        self._add_line_edit("additional_info", "Siguientes pasos", multiline=True)
        self._add_line_edit("remote_steps", "Notas de troubleshooting", multiline=True)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        refresh_button = QPushButton("Recalcular progreso")
        refresh_button.clicked.connect(self._update_progress)
        button_layout.addWidget(refresh_button)
        outer_layout.addLayout(button_layout)

    def _add_line_edit(self, field_name: str, label: str, *, multiline: bool = False) -> None:
        if multiline:
            widget: QWidget = QTextEdit()
            widget.setProperty("field_name", field_name)
            widget.textChanged.connect(partial(self._on_text_changed, field_name))
        else:
            line_edit = QLineEdit()
            line_edit.setProperty("field_name", field_name)
            line_edit.textChanged.connect(partial(self._on_line_changed, field_name))
            widget = line_edit
        self._field_widgets[field_name] = widget
        self._form_layout.addRow(QLabel(label), widget)

    # ------------------------------------------------------------------ Data sync
    def _populate_from_case(self) -> None:
        for field, widget in self._field_widgets.items():
            value = getattr(self.case, field, "")
            if isinstance(widget, QLineEdit):
                widget.blockSignals(True)
                widget.setText(str(value or ""))
                widget.blockSignals(False)
            elif isinstance(widget, QTextEdit):
                widget.blockSignals(True)
                widget.setPlainText(str(value or ""))
                widget.blockSignals(False)
        self._update_progress()

    def _on_line_changed(self, field: str, text: str) -> None:
        setattr(self.case, field, text)
        self.case.last_modified = ""
        self._schedule_autosave()
        self._update_progress()

    def _on_text_changed(self, field: str) -> None:
        widget = self._field_widgets.get(field)
        if isinstance(widget, QTextEdit):
            setattr(self.case, field, widget.toPlainText())
            self.case.last_modified = ""
            self._schedule_autosave()
            self._update_progress()

    def _schedule_autosave(self) -> None:
        if not self._autosave_enabled:
            return
        self._autosave_timer.start(self.AUTOSAVE_DEBOUNCE_MS)

    def _perform_autosave(self) -> None:
        if not self._autosave_enabled:
            return
        try:
            save_autosave(self.case)
        except Exception as exc:  # pragma: no cover - defensive UI path
            LOGGER.error("Autosave failed: %%s", exc)
            QMessageBox.warning(self, "Autosave", f"No se pudo guardar: {exc}")

    def _toggle_autosave(self, state: int) -> None:
        self._autosave_enabled = state == Qt.Checked
        if not self._autosave_enabled:
            self._autosave_timer.stop()

    def _update_progress(self) -> None:
        filled = 0
        total = 0
        for category, fields in self._categories.items():
            cat_total = len(fields)
            cat_filled = sum(1 for field in fields if bool(getattr(self.case, field, "").strip()))
            total += cat_total
            filled += cat_filled
            bar = self._category_bars.get(category)
            if bar:
                value = int((cat_filled / cat_total) * 100) if cat_total else 0
                bar.setValue(value)
        overall = int((filled / total) * 100) if total else 0
        self._overall_progress.setValue(overall)

    # ------------------------------------------------------------------ API
    def set_case(self, case: CaseData) -> None:
        self.case = case
        self._populate_from_case()

    def current_case(self) -> CaseData:
        return self.case

    def on_manual_autosave(self, callback: Callable[[CaseData], None]) -> None:
        """Allow the parent window to run extra hooks when autosave triggers."""

        def _handler() -> None:
            callback(self.case)

        self._autosave_timer.timeout.connect(_handler)

    def autosave_enabled(self) -> bool:
        return self._autosave_enabled

    def set_autosave_enabled(self, enabled: bool) -> None:
        self._autosave_enabled = enabled
        self._autosave_toggle.blockSignals(True)
        self._autosave_toggle.setChecked(enabled)
        self._autosave_toggle.blockSignals(False)
        if not enabled:
            self._autosave_timer.stop()
