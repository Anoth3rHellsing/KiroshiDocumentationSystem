#!/bin/bash
# Build the Kiroshi Documentation System into a standalone executable.
# This script requires PyInstaller to be installed.

set -e
pyinstaller --onefile --name KiroshiDocumentationSystem --collect-all streamlit run_app.py
