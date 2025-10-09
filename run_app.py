"""Entry point script to run Kiroshi Documentation System via Streamlit.
This wrapper allows packaging the Streamlit app into a standalone executable
using tools like PyInstaller.
"""

import runpy
import sys

import streamlit.web.cli as stcli
from streamlit.runtime.scriptrunner import get_script_run_ctx

def main():
    """Launch the Streamlit application."""
    # When executed via ``streamlit run run_app.py`` there is already an active
    # Streamlit runtime. Spawning a new CLI instance results in
    # ``RuntimeError: Runtime instance already exists``. Detect this situation
    # and directly execute the actual Streamlit script instead.
    if get_script_run_ctx() is not None:
        runpy.run_path("case_documentation_app.py", run_name="__main__")
        return

    # When the script is executed normally (e.g. packaged executable) launch
    # the Streamlit CLI so the app starts as expected.
    sys.argv = ["streamlit", "run", "case_documentation_app.py"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
