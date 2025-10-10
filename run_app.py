"""Entry point script to run Kiroshi Documentation System via Streamlit.
This wrapper allows packaging the Streamlit app into a standalone executable
using tools like PyInstaller.
"""

import os
from pathlib import Path
import sys

import streamlit.web.cli as stcli
from streamlit.runtime.scriptrunner import get_script_run_ctx


def _resolve_app_path() -> Path:
    """Return the absolute path to ``case_documentation_app.py``.

    When the project is frozen with PyInstaller the source files are unpacked
    into ``sys._MEIPASS``.  During local development the module lives next to
    this wrapper file.  Resolving the path in one place keeps the Streamlit
    launch command working in both scenarios.
    """


def _resolve_app_path() -> Path:
    """Return the absolute path to ``case_documentation_app.py``.


def _resolve_app_path() -> Path:
    """Return the absolute path to ``case_documentation_app.py``.

    When the project is frozen with PyInstaller the source files are unpacked
    into ``sys._MEIPASS``.  During local development the module lives next to
    this wrapper file.  Resolving the path in one place keeps the Streamlit
    launch command working in both scenarios.
    """

    base_dir = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_dir) / "case_documentation_app.py"


def _harmonize_security_settings() -> None:
    """Keep Streamlit's security flags consistent to avoid startup warnings."""

    cors_flag = os.environ.get("STREAMLIT_SERVER_ENABLE_CORS")
    if cors_flag and cors_flag.lower() in {"0", "false", "no"}:
        os.environ.setdefault("STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION", "false")


def main() -> None:
    """Launch the Streamlit application."""

    _harmonize_security_settings()

    app_path = _resolve_app_path()
    if not app_path.exists():
        raise FileNotFoundError(
            "Unable to locate case_documentation_app.py. "
            "If you created an executable with PyInstaller, make sure the "
            "script is bundled using '--add-data case_documentation_app.py;.'"
        )

    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
