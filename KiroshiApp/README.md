# Kiroshi Desktop Client

A PySide6 front-end that mirrors the Streamlit tooling for documenting and
tracking Kiroshi support cases. The desktop client uses a tabbed
`QMainWindow` hosted in the `KiroshiApp` package and can be launched directly
from the repository root.

## Features

- **Multi-tab case workspace:** Case, Email, Hardware Issues, Tables,
  Save/Load, Dashboard, Debug, and Settings tabs wrap the shared business
  logic from `KiroshiApp.core` so the desktop UI stays in sync with the
  Streamlit experience.
- **Hotkeys and clipboard parity:** Global shortcuts (Ctrl+Alt+1…8 and
  Ctrl+Alt+C) mirror the Streamlit copy-to-clipboard behaviour and are scoped
  to the active case.
- **Productivity flows:** Autosave/autoload, tracked-case dashboards, database
  snapshots, tutorial/tooltips, PDF export hooks, and second-line gating are
  wired into the same JSON/TrackedCases formats used by the web app.
- **AI copilot:** Integrated chat window and email drafting powered by the
  bundled AI client, with responses tied to the active case context.

## Getting Started

1. Clone the repository (or switch to the experimental branch if you already
   have a clone):

   ```bash
   git checkout codex/experimental-desktop-rebuild
   ```

2. Create and activate a virtual environment in the repository **root**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1
   ```

3. Install the desktop client dependencies from the repository root:

   ```bash
   pip install -r requirements.txt
   ```

4. Launch the application **from the repository root** so Python can resolve the
   `KiroshiApp` package:

   ```bash
   python -m KiroshiApp.main
   ```

   Running the module from inside the `KiroshiApp/` directory will raise
   `ModuleNotFoundError: No module named 'KiroshiApp'` because the package is on
   `PYTHONPATH` only when executed from the repository root.
