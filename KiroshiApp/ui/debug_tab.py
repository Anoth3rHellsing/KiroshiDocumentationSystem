"""Debug tab with protected access and diagnostic utilities."""
from __future__ import annotations

import json
import platform
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.logs import LogSnapshot, load_recent_logs, resolve_log_file_path
from KiroshiApp.core.storage import get_database_root

from KiroshiApp.core.model import CaseData


class DebugTab(QWidget):
    """Debugging utilities protected behind a simple admin login."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._label = QLabel("Debug tab coming soon", self)
        layout.addWidget(self._label)

    def refresh_case(self, case: CaseData) -> None:
        """Show debugging information for the active case."""

        summary = case.case_id or case.last_modified or "Sin caso seleccionado"
        self._label.setText(f"Debug tab coming soon\nCaso activo: {summary}")
