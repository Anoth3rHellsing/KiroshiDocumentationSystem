# Kiroshi Desktop Prototype (Experimental Branch)

This directory contains the experimental PySide6 rebuild of the Kiroshi
application. The branch focuses on validating a desktop-first architecture with
autosave, document generation, AI assistance, and background workers that keep
the UI responsive while long-running jobs execute.

## Requirements

Install the desktop dependencies before running the prototype:

```bash
pip install -r requirements.txt
```

Key packages include PySide6, ReportLab, pandas, openpyxl, requests, Pillow,
pytesseract, transformers, and openai.

## Structure
- `main.py`: Entry point that wires the logging stack and launches the desktop
  shell.
- `ui/`: User interface modules and Qt Designer files.
- `core/`: Core application logic and services.
-   `core/model.py`: Dataclasses representing cases, tracking metadata and
    remote sessions with JSON serialisation helpers.
-   `core/storage.py`: Autosave and persistence helpers that target the
    `KiroshiDatabase` folder on the local machine.
-   `core/pdf_generator.py`: ReportLab powered PDF exports for case
    summaries.
-   `core/attachments.py`: File-system helpers to manage per-case
    attachments and ZIP bundles.
-   `core/ai_client.py`: Abstraction layer for cloud, local API, or local
    transformers completions.
-   `core/tracking.py`: Utilities for reading and writing tracked case
    records.
-   `core/utils.py`: Shared helpers for logging, timestamps, and
    configuration files.
- `assets/`: Static assets such as icons, fonts, and shared QSS themes.
- `tests/`: Automated tests covering persistence, AI client backends, PDF
  exports, and end-to-end flows for the experimental desktop.

The desktop shell includes background workers for AI, PDF, and ZIP actions,
rotating log files under `core/logs/`, and a switchable light/dark theme that can
be toggled from the settings tab.

## Running the prototype

1. (Optional) Set `QT_QPA_PLATFORM=offscreen` when running on a headless
   environment.
2. Launch the app with:

   ```bash
   python -m KiroshiApp.main
   ```
3. The application loads any `autosave.json` found under the local
   `KiroshiDatabase` folder and opens the main window with the case, email,
   tracking, settings, and debug tabs ready for editing.

## Automated QA & testing

A pytest suite validates the critical behaviours of the prototype:

- `tests/test_storage.py`: autosave and persistent case storage helpers.
- `tests/test_ai_client.py`: AI client prompt formatting and backend dispatching.
- `tests/test_pdf_generator.py`: ReportLab PDF generation with attachments.
- `tests/test_desktop_flow.py`: End-to-end case flow (autosave → PDF export →
  tracking → closure).
- `tests/test_ui_performance.py`: Confirms the main window initialises in under
  two seconds when run off-screen.

Execute the full desktop suite with:

```bash
pytest tests/test_storage.py \
       tests/test_ai_client.py \
       tests/test_pdf_generator.py \
       tests/test_desktop_flow.py \
       tests/test_ui_performance.py
```

> **Note:** This branch remains experimental and is not intended for production
> deployments yet.

## Building a distributable binary

Use PyInstaller to generate a standalone executable of the experimental
prototype. The command below matches the Windows packaging flow proposed for the
desktop rebuild:

```bash
pyinstaller --noconsole --onefile KiroshiApp/main.py
```

If you have a custom icon available locally, add `--icon=/path/to/icon.ico` to
the command above. The repository omits binary assets so that you can supply
branding files that match your deployment requirements.

The produced binary will be written to the `dist/` directory. Bundle the
resulting executable with any additional resources required by the installer
workflow (for example an NSIS script) before distributing it to testers.
