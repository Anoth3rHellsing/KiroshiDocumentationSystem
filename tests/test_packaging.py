"""Tests for packaging helpers used by the Streamlit launcher and spec file."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import run_app


def test_resolve_app_path_unfrozen(monkeypatch: pytest.MonkeyPatch) -> None:
    """When not frozen the app path resolves relative to ``run_app.py``."""

    monkeypatch.delattr(run_app.sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(run_app.sys, "frozen", False, raising=False)

    expected = Path(run_app.__file__).resolve().parent / "case_documentation_app.py"
    assert run_app._resolve_app_path() == expected


def test_resolve_app_path_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """PyInstaller bundles should resolve paths using ``sys._MEIPASS``."""

    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    monkeypatch.setattr(run_app.sys, "_MEIPASS", bundle_dir, raising=False)
    monkeypatch.setattr(run_app.sys, "frozen", True, raising=False)

    expected = bundle_dir / "case_documentation_app.py"
    assert run_app._resolve_app_path() == expected


def test_set_default_runtime_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default runtime environment flags should only apply when frozen."""

    monkeypatch.setattr(run_app.sys, "frozen", False, raising=False)
    monkeypatch.delenv("STREAMLIT_SERVER_PORT", raising=False)
    monkeypatch.delenv("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", raising=False)

    run_app._set_default_runtime_flags()

    assert "STREAMLIT_SERVER_PORT" not in os.environ
    assert "STREAMLIT_GLOBAL_DEVELOPMENT_MODE" not in os.environ

    monkeypatch.setattr(run_app.sys, "frozen", True, raising=False)

    run_app._set_default_runtime_flags()

    assert os.environ["STREAMLIT_SERVER_PORT"] == "8502"
    assert os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] == "false"


@pytest.mark.parametrize(
    "cors_value, xsrf_expected",
    [
        ("false", "false"),
        ("0", "false"),
        ("no", "false"),
    ],
)
def test_harmonize_security_settings_disables_xsrf(
    monkeypatch: pytest.MonkeyPatch, cors_value: str, xsrf_expected: str
) -> None:
    """XSRF protection is turned off automatically when CORS is disabled."""

    monkeypatch.setenv("STREAMLIT_SERVER_ENABLE_CORS", cors_value)
    monkeypatch.delenv("STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION", raising=False)

    run_app._harmonize_security_settings()

    assert os.environ["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] == xsrf_expected


def test_harmonize_security_settings_respects_existing_xsrf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing XSRF configuration should remain untouched when set explicitly."""

    monkeypatch.setenv("STREAMLIT_SERVER_ENABLE_CORS", "false")
    monkeypatch.setenv("STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION", "true")

    run_app._harmonize_security_settings()

    assert os.environ["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] == "true"


def test_spec_import_generates_icon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Importing the spec file should generate an ICO file in the temp directory."""

    project_root = Path(__file__).resolve().parents[1]
    source_spec = project_root / "KiroshiDocumentationSystem.spec"
    copied_spec = tmp_path / "KiroshiDocumentationSystem.spec"
    copied_spec.write_text(source_spec.read_text(), encoding="utf-8")

    source_png = project_root / "Kiroshi_Logo.png"
    copied_png = tmp_path / "Kiroshi_Logo.png"
    copied_png.write_bytes(source_png.read_bytes())

    class _FakeImage:
        def __init__(self, image_path: Path) -> None:
            self.image_path = Path(image_path)

        def save(self, target: Path, format: str, sizes: list[tuple[int, int]]) -> None:  # noqa: ARG002
            Path(target).write_bytes(b"ICO")

    class _FakeImageModule:
        @staticmethod
        def open(path: Path) -> _FakeImage:  # noqa: D401
            return _FakeImage(path)

    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = _FakeImageModule  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)

    fake_pyinstaller = types.ModuleType("PyInstaller")
    fake_pyinstaller.__path__ = []  # mark as package
    fake_utils = types.ModuleType("PyInstaller.utils")
    fake_utils.__path__ = []
    fake_hooks = types.ModuleType("PyInstaller.utils.hooks")

    def _fake_collect_all(name: str) -> tuple[list[tuple[str, str]], list[str], list[str]]:  # noqa: ARG001
        return ([], [], [])

    fake_hooks.collect_all = _fake_collect_all  # type: ignore[attr-defined]
    fake_utils.hooks = fake_hooks  # type: ignore[attr-defined]
    fake_pyinstaller.utils = fake_utils  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "PyInstaller", fake_pyinstaller)
    monkeypatch.setitem(sys.modules, "PyInstaller.utils", fake_utils)
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", fake_hooks)

    module_name = "KiroshiDocumentationSystem.spec"
    loader = importlib.machinery.SourceFileLoader(module_name, str(copied_spec))
    spec = importlib.util.spec_from_file_location(module_name, copied_spec, loader=loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    class _FakeAnalysis:
        def __init__(self, *args, **kwargs) -> None:  # noqa: D401, ARG002
            self.pure: list[object] = []
            self.zipped_data: list[object] = []
            self.scripts: list[object] = []
            self.binaries: list[object] = []
            self.datas: list[object] = []

    module.Analysis = lambda *args, **kwargs: _FakeAnalysis()  # type: ignore[attr-defined]
    module.PYZ = lambda *args, **kwargs: object()  # type: ignore[attr-defined]
    module.EXE = lambda *args, **kwargs: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    generated_icon = module.ICON_PATH
    assert generated_icon == tmp_path / "Kiroshi_Logo.ico"
    assert generated_icon.exists()
