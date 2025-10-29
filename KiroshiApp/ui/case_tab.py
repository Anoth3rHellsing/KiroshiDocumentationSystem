"""Case tab implementation for the experimental desktop prototype."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.model import CaseData, TrackingData


class CaseTab(QWidget):
    """Display the active case and provide tracking controls."""

    startTrackingRequested = Signal(CaseData)
    stopTrackingRequested = Signal(str)

    def __init__(
        self,
        case: CaseData | None = None,
        *,
        second_line_enabled: bool = False,
    ) -> None:
        super().__init__()
        self._case = case or CaseData()
        self._second_line_enabled = second_line_enabled

        self._title_label = QLabel()
        self._title_label.setObjectName("caseTitleLabel")
        self._title_label.setWordWrap(True)

        details_group = QGroupBox("Detalles del caso")
        details_layout = QFormLayout(details_group)
        details_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._company_value = QLabel()
        self._case_id_value = QLabel()
        self._summary_value = QLabel()
        self._summary_value.setWordWrap(True)

        details_layout.addRow("Cliente", self._company_value)
        details_layout.addRow("Caso", self._case_id_value)
        details_layout.addRow("Descripción", self._summary_value)

        tracking_group = QGroupBox("Seguimiento")
        tracking_layout = QFormLayout(tracking_group)
        tracking_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._tracking_priority = QLabel()
        self._tracking_status = QLabel()
        self._tracking_ticket = QLabel()

        tracking_layout.addRow("Prioridad", self._tracking_priority)
        tracking_layout.addRow("Estado", self._tracking_status)
        tracking_layout.addRow("Ticket", self._tracking_ticket)

        self._tracking_banner = QLabel()
        self._tracking_banner.setWordWrap(True)
        self._tracking_banner.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._start_button = QPushButton("Iniciar seguimiento")
        self._start_button.clicked.connect(self._on_start_clicked)
        self._stop_button = QPushButton("Detener seguimiento")
        self._stop_button.clicked.connect(self._on_stop_clicked)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self._start_button)
        button_layout.addWidget(self._stop_button)
        button_layout.addStretch(1)

        self._dashboard_label = QLabel()
        self._dashboard_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title_label)
        layout.addWidget(details_group)
        layout.addWidget(tracking_group)
        layout.addWidget(self._tracking_banner)
        layout.addLayout(button_layout)
        layout.addWidget(self._dashboard_label)
        layout.addStretch(1)

        self.set_case(self._case)
        self.set_second_line_enabled(self._second_line_enabled)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_case(self, case: CaseData) -> None:
        """Load the provided case into the tab."""

        self._case = replace(case) if isinstance(case, CaseData) else CaseData()
        tracking = self._case.tracking if isinstance(self._case.tracking, TrackingData) else TrackingData()
        self._case.tracking = tracking

        self._title_label.setText(
            f"{self._case.company_name or 'Caso sin nombre'} — {self._case.brief_description or 'Sin resumen'}"
        )
        self._company_value.setText(self._case.company_name or "—")
        self._case_id_value.setText(self._case.case_id or "—")
        self._summary_value.setText(self._case.brief_description or self._case.description or "—")

        self._tracking_priority.setText(tracking.priority or "Normal")
        self._tracking_status.setText(tracking.status or "Sin seguimiento")
        self._tracking_ticket.setText(tracking.ticket_number or "—")

        self.update_tracking_state(tracking.active, tracking.status)

    def update_tracking_state(self, active: bool, status: str | None = None) -> None:
        """Refresh the banner and button state when tracking changes."""

        tracking = self._case.tracking if isinstance(self._case.tracking, TrackingData) else TrackingData()
        tracking.active = active
        if status is not None:
            tracking.status = status

        if active:
            message = "Seguimiento activo — el caso aparece en Control Tower y recordatorios."
            self._tracking_status.setText(tracking.status or "En monitoreo")
        else:
            message = "Seguimiento desactivado. Pulsa \"Iniciar seguimiento\" para enviar el caso al dashboard."
            self._tracking_status.setText(tracking.status or "Sin seguimiento")
        self._tracking_banner.setText(message)

        self._start_button.setEnabled(self._second_line_enabled and not active)
        self._stop_button.setEnabled(self._second_line_enabled and active)

    def set_second_line_enabled(self, enabled: bool) -> None:
        """Enable/disable tracking actions based on the 2nd Line mode."""

        self._second_line_enabled = enabled
        self._start_button.setEnabled(enabled and not self._case.tracking.active)
        self._stop_button.setEnabled(enabled and self._case.tracking.active)
        if enabled:
            self._dashboard_label.setText(
                "Dashboards activos: Control Tower y atajos de tracking disponibles (Ctrl+T)."
            )
        else:
            self._dashboard_label.setText(
                "Activa el modo 2nd Line en la pestaña Configuración para habilitar dashboards y atajos."
            )

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        if not self._case.case_id:
            self._tracking_banner.setText(
                "Asigna un ID de caso antes de iniciar el seguimiento."
            )
            return
        self._case.tracking.active = True
        self._case.tracking.status = self._case.tracking.status or "En monitoreo"
        self.update_tracking_state(True, self._case.tracking.status)
        self.startTrackingRequested.emit(self._case)

    def _on_stop_clicked(self) -> None:
        if not self._case.case_id:
            return
        self._case.tracking.active = False
        self.update_tracking_state(False, "Sin seguimiento")
        self.stopTrackingRequested.emit(self._case.case_id)
