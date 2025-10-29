"""Save/Load tab for managing persisted cases."""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Iterable

from PySide6.QtCore import Qt, QEvent, QThreadPool
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.attachments import create_zip
from ..core.model import CaseData
from ..core.storage import iter_case_files, load_case, save_case, save_autosave
from ..core.utils import get_database_root
from .background import run_in_threadpool

LOGGER = logging.getLogger(__name__)


class SaveLoadTab(QWidget):
    """Allow the user to persist, restore and export case information."""

    def __init__(
        self,
        case_getter: Callable[[], CaseData],
        case_setter: Callable[[CaseData], None],
        autosave_toggle: Callable[[bool], None] | None = None,
        *,
        autosave_db_enabled: bool = True,
        on_autosave_db_changed: Callable[[bool], None] | None = None,
        thread_pool: QThreadPool | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._case_getter = case_getter
        self._case_setter = case_setter
        self._autosave_toggle = autosave_toggle
        self._autosave_db_callback = on_autosave_db_changed
        self._thread_pool = thread_pool or QThreadPool.globalInstance()

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Case ID", "Compañía", "Modificado", "Ruta"])
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._autosave_checkbox = QCheckBox("Autosave to DB")
        self._autosave_checkbox.setChecked(autosave_db_enabled)
        self._autosave_checkbox.stateChanged.connect(self._on_autosave_state_changed)

        self._case_cache: "OrderedDict[str, tuple[float, CaseData]]" = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_limit = 48
        self._has_loaded = False
        self._loading = False
        self._queued_refresh = False

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(self._table)
        layout.addWidget(self._autosave_checkbox)

        button_row = QHBoxLayout()
        save_button = QPushButton("Guardar")
        save_button.clicked.connect(self._on_save_clicked)
        button_row.addWidget(save_button)

        load_button = QPushButton("Cargar")
        load_button.clicked.connect(self._on_load_clicked)
        button_row.addWidget(load_button)

        export_button = QPushButton("Exportar ZIP")
        export_button.clicked.connect(self._on_export_zip)
        button_row.addWidget(export_button)

        button_row.addStretch()
        refresh_button = QPushButton("Actualizar lista")
        refresh_button.clicked.connect(self.refresh_recent_cases)
        button_row.addWidget(refresh_button)

        layout.addLayout(button_row)

    # ------------------------------------------------------------------ Qt events
    def showEvent(self, event: QEvent) -> None:  # pragma: no cover - UI dispatch
        super().showEvent(event)
        self.ensure_loaded()

    # ------------------------------------------------------------------ callbacks
    def _on_autosave_state_changed(self, state: int) -> None:
        enabled = state == Qt.Checked
        if self._autosave_toggle:
            self._autosave_toggle(enabled)
        if self._autosave_db_callback:
            self._autosave_db_callback(enabled)
        if enabled:
            try:
                save_autosave(self._case_getter())
            except Exception as exc:  # pragma: no cover - defensive path
                LOGGER.warning("Autosave refresh failed: %s", exc)

    def _on_save_clicked(self) -> None:
        case = self._case_getter()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar caso",
            str(get_database_root()),
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            save_case(case, Path(path))
        except Exception as exc:  # pragma: no cover - defensive path
            QMessageBox.warning(self, "Guardar", f"No se pudo guardar: {exc}")
            LOGGER.error("Failed to save case: %s", exc)
            return
        self.refresh_recent_cases()

    def _on_load_clicked(self) -> None:
        selected = self._selected_path()
        path = selected or QFileDialog.getOpenFileName(
            self,
            "Cargar caso",
            str(get_database_root()),
            "JSON (*.json)",
        )[0]
        if not path:
            return
        try:
            case = load_case(Path(path))
        except Exception as exc:  # pragma: no cover
            QMessageBox.warning(self, "Cargar", f"No se pudo cargar el caso: {exc}")
            LOGGER.error("Failed to load case: %s", exc)
            return
        self._case_setter(case)
        QMessageBox.information(self, "Cargar", "Caso cargado correctamente")

    def _on_export_zip(self) -> None:
        selected = self._selected_path()
        if not selected:
            QMessageBox.information(self, "Exportar", "Selecciona un caso primero")
            return
        try:
            case = load_case(Path(selected))
        except Exception as exc:
            QMessageBox.warning(self, "Exportar", f"No se pudo cargar el caso: {exc}")
            LOGGER.error("Failed to load case for export: %s", exc)
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar adjuntos",
            str(get_database_root()),
            "ZIP (*.zip)",
        )
        if not destination:
            return

        def _on_success(_: Path) -> None:
            QMessageBox.information(self, "Exportar", "ZIP generado correctamente")

        def _on_error(exc: Exception) -> None:
            QMessageBox.warning(self, "Exportar", f"No se pudo crear el ZIP: {exc}")
            LOGGER.error("Failed to export zip: %s", exc)

        run_in_threadpool(
            create_zip,
            args=(case, Path(destination)),
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    # ------------------------------------------------------------------ helpers
    def _selected_path(self) -> str | None:
        selected = self._table.currentRow()
        if selected < 0:
            return None
        item = self._table.item(selected, 3)
        return item.text() if item else None

    def ensure_loaded(self) -> None:
        if self._has_loaded:
            return
        self.refresh_recent_cases()

    def refresh_recent_cases(self) -> None:
        if self._loading:
            self._queued_refresh = True
            return
        self._loading = True

        def _on_success(rows: list[tuple[str, str, str, str]]) -> None:
            self._apply_rows(rows)
            self._loading = False
            self._has_loaded = True
            if self._queued_refresh:
                self._queued_refresh = False
                self.refresh_recent_cases()

        def _on_error(exc: Exception) -> None:
            self._loading = False
            LOGGER.error("Failed to list recent cases: %s", exc)
            QMessageBox.warning(self, "Cargar", f"No se pudo listar los casos: {exc}")

        run_in_threadpool(
            self._collect_recent_rows,
            on_success=_on_success,
            on_error=_on_error,
            thread_pool=self._thread_pool,
        )

    def _collect_recent_rows(self) -> list[tuple[str, str, str, str]]:
        rows: list[tuple[str, str, str, str]] = []
        seen: set[str] = set()
        for path in list(iter_case_files())[:200]:
            try:
                case = self._load_case_cached(path)
            except Exception as exc:  # pragma: no cover - background logging
                LOGGER.debug("Skipping %s: %s", path, exc)
                continue
            identifier = f"{case.case_id}|{path}"
            if identifier in seen:
                continue
            seen.add(identifier)
            rows.append(
                (
                    case.case_id or "—",
                    case.company_name or "—",
                    case.last_modified or "",
                    str(path),
                )
            )
        rows.sort(key=lambda item: item[2], reverse=True)
        return rows

    def _load_case_cached(self, path: Path) -> CaseData:
        mtime = path.stat().st_mtime
        cache_key = str(path)
        with self._cache_lock:
            cached = self._case_cache.get(cache_key)
            if cached and cached[0] == mtime:
                self._case_cache.move_to_end(cache_key)
                return cached[1]
        case = load_case(path)
        with self._cache_lock:
            self._case_cache[cache_key] = (mtime, case)
            self._case_cache.move_to_end(cache_key)
            while len(self._case_cache) > self._cache_limit:
                self._case_cache.popitem(last=False)
        return case

    def _apply_rows(self, rows: Iterable[tuple[str, str, str, str]]) -> None:
        self._table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self._table.insertRow(row_idx)
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()
