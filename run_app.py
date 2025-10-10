"""Streamlit entry point for the Kiroshi Documentation System.

This lightweight wrapper mirrors the command `streamlit run
case_documentation_app.py` while remaining compatible with PyInstaller
builds.  When frozen, PyInstaller unpacks the project into a temporary
folder referenced by ``sys._MEIPASS``.  Resolving the application path at
runtime keeps the launcher functional whether the project is executed
from source or from the generated executable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit.web.cli as stcli


def _resolve_app_path() -> Path:
    """Return the absolute path to ``case_documentation_app.py``.

    In unfrozen runs the module lives next to this wrapper.  Inside a
    PyInstaller bundle it is extracted into ``sys._MEIPASS``.  The
    ``getattr`` call lets the same logic cover both scenarios without
    additional conditionals.
    """

    base_dir = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_dir) / "case_documentation_app.py"


def _harmonize_security_settings() -> None:
    """Keep Streamlit CORS and XSRF flags aligned when packaging."""

    cors_flag = os.environ.get("STREAMLIT_SERVER_ENABLE_CORS")
    if cors_flag and cors_flag.lower() in {"0", "false", "no"}:
        os.environ.setdefault("STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION", "false")


def _set_default_port() -> None:
    """Use port 8502 for frozen builds so the packaged URL is predictable."""

    if getattr(sys, "frozen", False) and "STREAMLIT_SERVER_PORT" not in os.environ:
        os.environ["STREAMLIT_SERVER_PORT"] = "8502"


def main() -> None:
    """Launch the Streamlit application via ``streamlit.web.cli``."""

    _harmonize_security_settings()
    _set_default_port()

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
