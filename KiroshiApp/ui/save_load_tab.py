"""Save/Load tab implementation for working with case files."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from KiroshiApp.core.model import CaseData
from KiroshiApp.core.storage import (
    cases_root,
    iter_case_files,
    load_autosave,
    load_case,
    save_case_to_db,
)


class SaveLoadTab(QWidget):
    """Widget that provides quick access to save and load actions."""

    def __init__(
        self,
        case_getter: Callable[[], CaseData],
        case_loader: Callable[[CaseData, str], None],
        *,
        base_path: Path | str | None = None,
    ) -> None:
        super().__init__()
        self._case_getter = case_getter
        self._case_loader = case_loader
        self._base_path = base_path
        self._cases_root = cases_root(base_path)

        self._current_case_label = QLabel(self)
        self._location_label = QLabel(self)
        self._recent_list = QListWidget(self)
        self._status_label = QLabel(self)

        self._build_ui()
        self.refresh_case(self._case_getter())
        self.refresh_recent_files()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._current_case_label.setObjectName("current-case-label")
        layout.addWidget(self._current_case_label)

        self._location_label.setText(f"Directorio de casos: {self._cases_root}")
        layout.addWidget(self._location_label)

        button_row = QHBoxLayout()
        save_button = QPushButton("Guardar caso actual", self)
        save_button.clicked.connect(self._save_current_case)
        button_row.addWidget(save_button)

        refresh_button = QPushButton("Actualizar lista", self)
        refresh_button.clicked.connect(self.refresh_recent_files)
        button_row.addWidget(refresh_button)

        load_selected_button = QPushButton("Cargar selección", self)
        load_selected_button.clicked.connect(self._load_selected_case)
        button_row.addWidget(load_selected_button)

        browse_button = QPushButton("Cargar archivo…", self)
        browse_button.clicked.connect(self._load_from_dialog)
        button_row.addWidget(browse_button)

        autosave_button = QPushButton("Load autosave", self)
        autosave_button.clicked.connect(self._load_autosave)
        button_row.addWidget(autosave_button)

        layout.addLayout(button_row)

        recent_label = QLabel("Casos recientes", self)
        recent_label.setObjectName("recent-label")
        layout.addWidget(recent_label)

        self._recent_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self._recent_list)

        self._status_label.setObjectName("status-label")
        layout.addWidget(self._status_label)

        layout.addStretch()

    def refresh_case(self, case: CaseData) -> None:
        """Update the header with the currently active case."""

        summary_parts = [
            value.strip()
            for value in (case.case_id, case.company_name, case.brief_description)
            if isinstance(value, str)
        ]
        summary = next((part for part in summary_parts if part), "Sin datos de caso")
        self._current_case_label.setText(f"Caso activo: {summary}")

    def refresh_recent_files(self) -> None:
        """Reload the list of recently saved case files."""

        self._recent_list.clear()
        has_items = False
        for path in iter_case_files(base_path=self._base_path):
            has_items = True
            display_text = f"{path.name} • {self._format_mtime(path)}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, path)
            self._recent_list.addItem(item)

        if not has_items:
            placeholder = QListWidgetItem("No hay casos guardados todavía")
            placeholder.setFlags(Qt.NoItemFlags)
            self._recent_list.addItem(placeholder)

    def _format_mtime(self, path: Path) -> str:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return "desconocido"
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

    def _save_current_case(self) -> None:
        case = self._case_getter()
        try:
            destination = save_case_to_db(case, base_path=self._base_path)
        except OSError as exc:  # pragma: no cover - filesystem errors are rare
            self._status_label.setText(f"Error al guardar el caso: {exc}")
            return
        self._status_label.setText(f"Caso guardado en {destination}")
        self.refresh_recent_files()

    def _load_selected_case(self) -> None:
        item = self._recent_list.currentItem()
        if item is None or not item.flags() & Qt.ItemIsSelectable:
            self._status_label.setText("Selecciona un archivo para cargar.")
            return
        path = item.data(Qt.UserRole)
        if not isinstance(path, Path):
            self._status_label.setText("La selección no es un archivo válido.")
            return
        self._load_case_from_path(path)

    def _load_from_dialog(self) -> None:
        start_directory = str(self._cases_root)
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de caso",
            start_directory,
            "Archivos JSON (*.json)",
        )
        if not filename:
            return
        self._load_case_from_path(Path(filename))

    def _load_case_from_path(self, path: Path) -> None:
        case = load_case(path)
        self._case_loader(case, str(path))
        self._status_label.setText(f"Caso cargado desde {path}")
        self.refresh_recent_files()

    def _load_autosave(self) -> None:
        case = load_autosave(base_path=self._base_path)
        if case is None:
            self._status_label.setText("No se encontró un autosave disponible.")
            return
        self._case_loader(case, "autosave")
        self._status_label.setText("Autosave cargado correctamente.")
        self.refresh_recent_files()
