# Kiroshi Desktop Prototype (Experimental Branch)

This branch hosts an experimental PySide6 rewrite of the Kiroshi desktop tools.
The current goal is to validate the project structure and launch a minimal
placeholder window that future phases will extend.

## Getting Started

```bash
git checkout codex/experimental-desktop-rebuild
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m KiroshiApp.main
```

The application will open an empty main window while additional functionality
is implemented in later phases.
