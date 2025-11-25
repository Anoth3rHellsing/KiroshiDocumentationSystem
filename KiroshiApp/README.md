# Kiroshi Desktop Prototype (Experimental Branch)

This branch hosts an experimental PySide6 rewrite of the Kiroshi desktop tools.
The current goal is to validate the project structure and launch a minimal
placeholder window that future phases will extend.

## Getting Started

1. Clone the repository (or switch to the experimental branch if you already
   have a clone):

   ```bash
   git checkout codex/experimental-desktop-rebuild
   ```

2. Create and activate a virtual environment in the repository **root**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
   ```

3. Install the desktop prototype dependencies from the repository root:

   ```bash
   pip install -r requirements.txt
   ```

4. Launch the prototype **from the repository root** so Python can resolve the
   `KiroshiApp` package:

   ```bash
   python -m KiroshiApp.main
   ```

   Running the module from inside the `KiroshiApp/` directory will raise
   `ModuleNotFoundError: No module named 'KiroshiApp'` because the package is
   no longer on `PYTHONPATH`.

The application will open an empty main window while additional functionality
is implemented in later phases.

## Knowledge updates

- See `docs/ai_research_notes.md` for a curated digest of 3Shape Help Center highlights and community-sourced troubleshooting themes (Facebook, Reddit) with Dell/IT context for AI-assisted responses.
