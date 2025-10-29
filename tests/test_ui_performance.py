from __future__ import annotations

import os
import time

import pytest

try:  # pragma: no cover - depends on GUI availability
    from PySide6.QtWidgets import QApplication
except Exception as exc:  # pragma: no cover - skip when Qt is unavailable
    pytest.skip(f"PySide6 QtWidgets unavailable: {exc}", allow_module_level=True)

from KiroshiApp.core.model import CaseData


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_startup_is_fast(qt_app: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from KiroshiApp.ui import main_window as main_window_module

    monkeypatch.setattr(
        "KiroshiApp.core.utils.get_database_root",
        lambda base_path=None: tmp_path,
        raising=False,
    )
    monkeypatch.setattr(
        main_window_module,
        "get_database_root",
        lambda base_path=None: tmp_path,
        raising=False,
    )
    monkeypatch.setattr(main_window_module, "load_global_config", lambda base_path=None: {}, raising=False)
    monkeypatch.setattr(
        main_window_module,
        "save_global_config",
        lambda config, base_path=None: tmp_path / "settings.json",
        raising=False,
    )

    case = CaseData(company_name="Acme", case_id="CASE-UI", brief_description="Startup timing")

    start = time.perf_counter()
    window = main_window_module.KiroshiMainWindow(case=case)
    elapsed = time.perf_counter() - start

    try:
        assert elapsed < 2.0
    finally:
        window.close()
        window.deleteLater()
