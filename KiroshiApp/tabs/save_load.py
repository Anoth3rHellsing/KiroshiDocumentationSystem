from __future__ import annotations

import json
from pathlib import Path

from PySide6 import QtWidgets

from KiroshiApp.state import CaseState
from .base import BaseSectionWidget


class SaveLoadTab(BaseSectionWidget):
    def __init__(self, case: CaseState, parent: QtWidgets.QWidget | None = None):
        super().__init__("Save/Load", case, parent)
        self.info_label = QtWidgets.QLabel("Persist case data alongside Streamlit JSON formats.")
        self.save_button = QtWidgets.QPushButton("Save snapshot")
        self.load_button = QtWidgets.QPushButton("Load snapshot")
        self.pdf_button = QtWidgets.QPushButton("Export PDF")
        self.save_button.clicked.connect(self._save_snapshot)
        self.load_button.clicked.connect(self._load_snapshot)
        self.pdf_button.clicked.connect(self._export_pdf)
        self.complete_checkbox = QtWidgets.QCheckBox("Snapshot verified")

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.save_button)
        row.addWidget(self.load_button)
        row.addWidget(self.pdf_button)
        row.addWidget(self.complete_checkbox)
        row.addStretch(1)

        self.layout.addWidget(self.info_label)
        self.layout.addLayout(row)
        self.apply_section_state()

    def _save_snapshot(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Case", filter="JSON Files (*.json)")
        if not path:
            return
        payload = self.case.to_dict()
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.update_completion(True, json.dumps(payload))
        QtWidgets.QMessageBox.information(self, "Saved", f"Snapshot saved to {path}")

    def _load_snapshot(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Case", filter="JSON Files (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Failed to load", str(exc))
            return
        restored = CaseState.from_dict(data)
        self.case.title = restored.title
        self.case.case_id = restored.case_id
        self.case.sections.update(restored.sections)
        self.case.attachments = restored.attachments
        self.apply_section_state()
        self.update_completion(True, json.dumps(data))
        QtWidgets.QMessageBox.information(self, "Loaded", f"Loaded {path}")

    def render_state(self, state):
        self.complete_checkbox.setChecked(state.completed)

    def _export_pdf(self) -> None:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except Exception as exc:  # pragma: no cover - optional dependency
            QtWidgets.QMessageBox.warning(
                self,
                "ReportLab missing",
                f"Install reportlab to enable PDF export. ({exc})",
            )
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export PDF", filter="PDF Files (*.pdf)")
        if not path:
            return
        c = canvas.Canvas(path, pagesize=letter)
        text = c.beginText(50, 750)
        text.setFont("Helvetica", 10)
        text.textLine(f"Case: {self.case.title} ({self.case.case_id})")
        for name, section in self.case.sections.items():
            text.textLine("")
            text.textLine(f"[{name}] {'✓' if section.completed else '✗'}")
            for line in section.content.splitlines():
                text.textLine(line)
        c.drawText(text)
        c.save()
        QtWidgets.QMessageBox.information(self, "Exported", f"PDF saved to {path}")
