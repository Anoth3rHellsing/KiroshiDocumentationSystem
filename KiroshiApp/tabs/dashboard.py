from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


def _database_dir() -> Path:
    if sys.platform.startswith("win"):
        candidate = Path("C:/ProgramFiles/KiroshiDatabase")
        if candidate.exists():
            return candidate
    return Path.home() / "KiroshiDatabase"


def load_tracked_cases() -> list[dict]:
    database_dir = _database_dir()
    tracked_dir = database_dir / "TrackedCases"
    cases: list[dict] = []
    for path in list(database_dir.glob("*.json")) + list(tracked_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tracking = data.get("tracking") or {}
        if tracking and not tracking.get("active", True):
            continue
        cases.append(
            {
                "path": str(path),
                "case_id": data.get("case_id") or path.stem,
                "company": data.get("company") or data.get("company_name") or "",
                "status": tracking.get("status") if isinstance(tracking, dict) else data.get("status", ""),
                "priority": tracking.get("priority") if isinstance(tracking, dict) else data.get("priority", ""),
            }
        )
    return cases


class DashboardTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Dashboard", case, parent)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Case ID", "Company", "Status", "Priority"])
        refresh_btn = QtWidgets.QPushButton("Refresh tracked cases")
        refresh_btn.clicked.connect(self.refresh)
        self.layout.addWidget(self.table)
        self.layout.addWidget(refresh_btn)
        self.refresh()
        self.update_completion(True, "dashboard")

    def refresh(self) -> None:
        cases = load_tracked_cases()
        self.table.setRowCount(len(cases))
        for row, item in enumerate(cases):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(item.get("case_id", "")))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(item.get("company", "")))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(item.get("status", "")))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(str(item.get("priority", ""))))
