# Kiroshi Desktop Prototype (Experimental Branch)

This repository hosts an experimental PySide6 rewrite of the Kiroshi
documentation tools. The goal of this branch is to validate the desktop app
structure and ship a minimal placeholder window that future phases will extend.

## Getting Started

Clone the repository (or switch to `codex/experimental-desktop-rebuild` if you
already have a clone), create a virtual environment in the repository **root**, and
install the prototype dependencies:

```bash
git checkout codex/experimental-desktop-rebuild
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Launch the desktop prototype **from the repository root** so Python can resolve
the `KiroshiApp` package:

```bash
python -m KiroshiApp.main
```

Running the module from inside the `KiroshiApp/` directory will raise
`ModuleNotFoundError: No module named 'KiroshiApp'` because the package is no
longer on `PYTHONPATH`.

The application currently opens an empty main window while additional
functionality is implemented in later phases.

## Repository Layout

The legacy Streamlit implementation and its supporting tooling have been
removed from this branch. The remaining structure focuses on the desktop
prototype:

- `KiroshiApp/` contains the PySide6 application code.
- `requirements.txt` lists the Python dependencies required by the prototype.
- `KiroshiApp/README.md` mirrors this guide for quick reference from within the
  package directory.

## Contributing

This branch is experimental and intentionally lightweight. Contributions should
focus on iterating on the desktop experience—new UI tabs, integrations, or
refinements to the existing placeholder workflows. Streamlit-specific features
belong on the mainline branch and are intentionally out of scope here.
