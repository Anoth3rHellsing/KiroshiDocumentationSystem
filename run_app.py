"""Entry point script to run Kiroshi Documentation System via Streamlit.
This wrapper allows packaging the Streamlit app into a standalone executable
using tools like PyInstaller.
"""

import sys
import streamlit.web.cli as stcli

def main():
    """Launch the Streamlit application."""
    sys.argv = ["streamlit", "run", "case_documentation_app.py"]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
