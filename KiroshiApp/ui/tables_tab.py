"""Spreadsheet-style view for case sections in the experimental prototype."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.model import CaseData, RemoteSessionEntry


def _humanize_label(attribute: str) -> str:
    return attribute.replace("_", " ").title()


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "N/A"
    text = str(value).strip()
    return text if text else "N/A"


def _format_multiline(value: str) -> str:
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" in cleaned:
        return "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned


RowBuilder = Callable[[CaseData], list[list[str]]]


@dataclass(frozen=True)
class SectionSpec:
    """Configuration describing how to render a case section."""

    name: str
    headers: Sequence[str]
    row_builder: RowBuilder
    call_label: str = "Int"

    def build_rows(self, case: CaseData) -> list[list[str]]:
        return self.row_builder(case)

    def build_title(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{self.name} ({self.call_label}) – {today}"


def _simple_fields(fields: Sequence[tuple[str, str | None]]) -> RowBuilder:
    normalized: list[tuple[str, str]] = []
    for attribute, label in fields:
        normalized.append((attribute, label or _humanize_label(attribute)))

    def _builder(case: CaseData) -> list[list[str]]:
        rows: list[list[str]] = []
        for attribute, label in normalized:
            raw = getattr(case, attribute, None)
            display = _format_value(raw)
            rows.append([label, display])
        return rows

    return _builder


def _remote_session_rows(case: CaseData) -> list[list[str]]:
    rows: list[list[str]] = []
    sessions: Iterable[RemoteSessionEntry] = getattr(case, "remote_sessions", []) or []
    for index, session in enumerate(sessions, start=1):
        title = session.display_title(index)
        notes = _format_value(session.notes)
        rows.append(
            [
                title,
                _format_multiline(notes if notes != "N/A" else ""),
                _format_value(session.created_at),
                _format_value(session.updated_at),
            ]
        )
    if not rows:
        rows.append(["No remote sessions recorded", "", "", ""])
    return rows


SECTION_SPECS: Sequence[SectionSpec] = (
    SectionSpec(
        name="PHONECALL",
        headers=("Field", "Value"),
        row_builder=_simple_fields(
            (
                ("caller_name", None),
                ("phone_description", "Call Summary"),
                ("email", None),
                ("dongle_number", "Dongle"),
                ("phone_number", "Callback Number"),
                ("teamviewer_id", "TeamViewer ID"),
                ("teamviewer_password", "TeamViewer Password"),
            )
        ),
        call_label="Phonecall",
    ),
    SectionSpec(
        name="INTERNAL NOTES",
        headers=("Field", "Value"),
        row_builder=_simple_fields(
            (
                ("internal_helpjuice", "Internal Notes"),
                ("internal_logs", "Internal Logs"),
            )
        ),
    ),
    SectionSpec(
        name="REMOTE SESSION",
        headers=("Field", "Value"),
        row_builder=_simple_fields(
            (
                ("remote_steps", "Remote Steps"),
                ("repro_steps", "Reproduction Steps"),
            )
        ),
    ),
    SectionSpec(
        name="REMOTE SESSIONS",
        headers=("Title", "Notes", "Created", "Updated"),
        row_builder=_remote_session_rows,
    ),
    SectionSpec(
        name="CONCLUSION",
        headers=("Field", "Value"),
        row_builder=_simple_fields(
            (
                ("root_cause", "Root Cause"),
                ("solution", "Solution"),
            )
        ),
    ),
    SectionSpec(
        name="AX COORDINATORS",
        headers=("Field", "Value"),
        row_builder=_simple_fields(
            (
                ("request_issue", "Request"),
                ("contact_name", "Contact Name"),
                ("office_ph", "Office Phone"),
                ("direct_ph", "Direct Phone"),
                ("best_time", "Best Time"),
                ("patterson", "Patterson"),
                ("straumann", "Straumann"),
            )
        ),
    ),
    SectionSpec(
        name="ESCALATION 2ND LINE",
        headers=("Field", "Value"),
        row_builder=_simple_fields(
            (
                ("esc_name", "Name"),
                ("esc_ph", "Phone"),
                ("esc_email", "Email"),
            )
        ),
    ),
)


class SectionWidget(QWidget):
    """Widget displaying a single case section with clipboard helpers."""

    def __init__(self, spec: SectionSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self._rows: list[list[str]] = []
        self._title: str = spec.build_title()

        wrapper = QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 16)

        header_row = QHBoxLayout()
        self.title_label = QLabel(self._title, self)
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px;")
        header_row.addWidget(self.title_label)
        header_row.addStretch(1)

        copy_title_btn = QPushButton("Copy title", self)
        copy_title_btn.clicked.connect(self.copy_title_to_clipboard)
        header_row.addWidget(copy_title_btn)

        copy_table_btn = QPushButton("Copy table", self)
        copy_table_btn.clicked.connect(self.copy_table_to_clipboard)
        header_row.addWidget(copy_table_btn)

        wrapper.addLayout(header_row)

        self.table = QTableWidget(self)
        self.table.setColumnCount(len(spec.headers))
        self.table.setHorizontalHeaderLabels(list(spec.headers))
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(True)
        wrapper.addWidget(self.table)

        divider = QFrame(self)
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        wrapper.addWidget(divider)

    def update_case(self, case: CaseData) -> None:
        self._title = self.spec.build_title()
        self.title_label.setText(self._title)
        self._rows = self.spec.build_rows(case)
        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setToolTip(value)
                self.table.setItem(row_idx, col_idx, item)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def copy_title_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._title)

    def copy_table_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.as_tsv(include_title=True))

    def as_tsv(self, *, include_title: bool = False) -> str:
        lines: list[str] = []
        if include_title:
            lines.append(self._title)
        lines.append("\t".join(self.spec.headers))
        for row in self._rows:
            sanitized = [cell.replace("\n", " ").strip() for cell in row]
            lines.append("\t".join(sanitized))
        return "\n".join(lines)

    @property
    def title_text(self) -> str:
        return self._title

    @property
    def rows(self) -> Sequence[Sequence[str]]:
        return tuple(tuple(cell for cell in row) for row in self._rows)

from KiroshiApp.core.model import CaseData


class TablesTab(QWidget):
    """Spreadsheet-style presentation of key case sections."""

    def __init__(self, case: CaseData | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.case = case or CaseData()
        self._section_widgets: list[SectionWidget] = []
        self._build_ui()
        self.update_case(self.case)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_content = QWidget(scroll_area)
        scroll_area.setWidget(scroll_content)

        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        for spec in SECTION_SPECS:
            section_widget = SectionWidget(spec, scroll_content)
            self._section_widgets.append(section_widget)
            content_layout.addWidget(section_widget)

        content_layout.addStretch(1)

    def update_case(self, case: CaseData) -> None:
        self.case = case
        for widget in self._section_widgets:
            widget.update_case(case)

    def section_count(self) -> int:
        return len(self._section_widgets)

    def section_at(self, index: int) -> SectionWidget | None:
        if 0 <= index < len(self._section_widgets):
            return self._section_widgets[index]
        return None

    def section_tsv(self, index: int) -> str:
        section = self.section_at(index)
        return section.as_tsv(include_title=True) if section else ""

    def all_sections_tsv(self) -> str:
        chunks = [widget.as_tsv(include_title=True) for widget in self._section_widgets]
        return "\n\n".join(chunk for chunk in chunks if chunk)


__all__ = ["TablesTab", "SECTION_SPECS", "SectionWidget", "SectionSpec"]

