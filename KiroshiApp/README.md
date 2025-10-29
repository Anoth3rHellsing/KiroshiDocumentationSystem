# KiroshiApp Experimental Desktop Rebuild

This directory hosts the experimental desktop implementation of the Kiroshi application.
The branch is dedicated to prototyping a PySide6-based interface with supporting
utilities for document generation and AI-assisted tooling.

## Structure
- `main.py`: Temporary entry point for the future desktop client.
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
- `tests/`: Automated tests for the desktop components.

The desktop shell now includes background workers for AI, PDF, and ZIP actions,
rotating log files under `core/logs/`, and a switchable light/dark theme that can
be toggled from the settings tab.

> **Note:** This branch is experimental and not intended for production use yet.
