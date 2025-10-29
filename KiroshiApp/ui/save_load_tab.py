"""Save/Load tab placeholder for the experimental desktop prototype."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SaveLoadTab(QWidget):
    """Simple placeholder widget until the real implementation arrives."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Save/Load tab coming soon"))
