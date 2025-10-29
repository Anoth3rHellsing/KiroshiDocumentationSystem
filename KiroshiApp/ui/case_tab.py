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

from KiroshiApp.core.model import CaseData


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
        self._label = QLabel("Case tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Display the case identifier so users know what is active."""

        summary = case.case_id or case.company_name or "Sin caso seleccionado"
        self._label.setText(f"Case tab coming soon\nCaso activo: {summary}")
