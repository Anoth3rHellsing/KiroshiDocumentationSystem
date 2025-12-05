#!/bin/bash
# Build the Kiroshi Documentation System into a standalone executable.
# This script requires streamlit-desktop-app to be installed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_ENTRY="case_documentation_app.py"
APP_NAME="KiroshiDesk"
DEFAULT_ICON="$SCRIPT_DIR/Kiroshi_Logo.png"

icon_specified=0
pyinstaller_options_specified=0
for arg in "$@"; do
    case "$arg" in
        --icon|--icon=*)
            icon_specified=1
            ;;
        --pyinstaller-options|--pyinstaller-options=*)
            pyinstaller_options_specified=1
            ;;
    esac
done

cmd=(streamlit-desktop-app build "$APP_ENTRY" --name "$APP_NAME")

if [[ $icon_specified -eq 0 && -f "$DEFAULT_ICON" ]]; then
    cmd+=(--icon "$DEFAULT_ICON")
fi

if [[ $pyinstaller_options_specified -eq 0 ]]; then
    cmd+=(--pyinstaller-options --uac-admin)
fi

if [[ $# -gt 0 ]]; then
    cmd+=("$@")
fi

echo "Running: ${cmd[*]}"
"${cmd[@]}"
