import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_pyside_stub() -> None:
    try:
        import PySide6  # noqa: F401
    except Exception:  # pragma: no cover - best effort shim for CI environments
        qt_gui = types.ModuleType("PySide6.QtGui")

        class _DummyPixmap:
            def isNull(self) -> bool:  # noqa: D401 - simple stub
                return True

            def save(self, *_args, **_kwargs) -> bool:
                return False

        class _DummyScreen:
            def grabWindow(self, *_args, **_kwargs) -> _DummyPixmap:
                return _DummyPixmap()

        class _DummyApp:
            @staticmethod
            def instance() -> None:
                return None

        qt_gui.QGuiApplication = _DummyApp
        qt_gui.QScreen = _DummyScreen

        pyside6 = types.ModuleType("PySide6")
        pyside6.__path__ = []  # type: ignore[attr-defined]
        pyside6.QtGui = qt_gui

        sys.modules["PySide6"] = pyside6
        sys.modules["PySide6.QtGui"] = qt_gui


_ensure_pyside_stub()
