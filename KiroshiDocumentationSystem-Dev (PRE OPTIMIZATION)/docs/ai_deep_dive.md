# Kiroshi Documentation System — Full Internal Blueprint

## Purpose of this document
This file is written as a dense, system-level map for an AI maintainer. It enumerates every control surface, data flow, and implicit contract inside the Kiroshi Documentation System so automated agents can modify or extend the codebase without reverse-engineering intent from the UI alone.

## Top-level entrypoint
- `run_app.py` is the only supported launcher. It computes the absolute path to `case_documentation_app.py` at runtime and rewrites `sys.argv` to call `streamlit.web.cli.main`, which keeps both source and PyInstaller builds aligned. When packaged, it resolves the unpacked path via `sys._MEIPASS` and harmonises Streamlit CORS/XSRF flags so desktop bundles behave like browser runs. The wrapper also pins default ports and development flags when `sys.frozen` is set, then exits through `stcli.main()` to hand off control to Streamlit.

## Primary application module (`case_documentation_app.py`)
The file is monolithic and owns nearly all runtime behaviour. Key architectural pillars:

### Import path management
- Inserts the repository root into `sys.path` before any sibling imports to keep local modules (`kiroshi_chat`, `kiroshi_cloud_sync`, `kiroshi_hotkeys`) available when the app is embedded inside Streamlit Desktop or PyInstaller bundles. This mirrors the bundling assumptions in `run_app.py` and prevents `ModuleNotFoundError` in frozen environments.

### Conditional capabilities and fallbacks
- Probes for GUI-dependent packages (ReportLab chart extras, `pyautogui`, `tkinter`, `PIL.ImageGrab`, `mss`) and exposes boolean flags so downstream code can disable UI elements or chart rendering gracefully. The `_require_reportlab_charts` helper raises a clear runtime error if chart rendering is attempted without the optional ReportLab components.

### Global constants and defaults
- Maintains version strings, autosave identifiers (`AUTOSAVE_FILE`, `AUTOSAVE_DIR`, `_AUTOSAVE_SESSION_ID`), telemetry defaults (OpenAI base URL, API key, AI mode), and file logging configuration. These constants drive UI labelling, persistence, and default model routing across the app and the chat helpers.

### Context managers and UI scaffolding
- Defines `safe_modal` to normalize modal usage across Streamlit versions. It prefers `st.modal` when available and falls back to a header-styled container, allowing modal-style flows without version pinning. This protects the numerous dialog interactions (error dialogs, confirmations) from breaking on older Streamlit builds.

### Data model and persistence
- Uses dataclasses extensively to represent case records and related payloads, enabling `asdict` conversions for JSON autosave/export. Autosave writes to `autosave.json` inside `autosaves/` with a session-specific ID so multiple sessions do not clobber each other. Manual save/load operates against the `C:/ProgramFiles/KiroshiDatabase` tree (or the Unix home equivalent) in lockstep with the cloud sync utilities.

### Tabs and functional surfaces
The UI is structured into tabs that share a common state store:
- **Case tab**: Captures customer metadata, notes, resolution steps, and toggles for tracking or hardware-specific fields. Completion meters reflect field coverage, and autosave is triggered after every meaningful interaction.
- **Email tab**: Builds templated prompts or full emails for multiple scenarios (customer recap, escalation, custom request). Customer name, company, case number, and summary are pre-injected to reduce manual edits.
- **Tables tab**: Renders category tables (build title, description, phone call notes, internal notes, remote session details, additional info, root cause/conclusion) with a dated title, and registers global clipboard hotkeys via `ensure_hotkey_listener`/`update_hotkey_snapshot` so agents can copy individual sections using Ctrl+Alt+1…8 without leaving the active window.
- **PDF export**: Assembles a ReportLab document with wrapped table cells and optional charts. Screenshot and attachment assets are bundled into a ZIP export, with logs stored under `logs/` and screenshots under `Screenshots/` to separate noisy files from critical artefacts.
- **Attachments & screenshots**: File uploader widgets collect supplementary artefacts. Screenshots are taken with `pyautogui`, `ImageGrab`, or `mss` depending on availability. Metadata is preserved so exported bundles remain context-rich.
- **Save/Load tab**: Persists cases by ID into the database directory, lists recent cases, and supports reloading into the current session. It also triggers tracking state changes when a case is reopened.
- **Case tracking and dashboard**: Dell/FedEx tracking fields are persisted under `TrackedCases` for second-line visibility. The dashboard summarises active items, allows closing/untracking, and feeds the global hotkeys selector.
- **Case Dex download**: Pulls a Case Dex package for a given case ID and stores it as a ZIP alongside other exports.
- **Debug tab**: Protected by `admin`/`admin` credentials and surfaces log-tail diagnostics (last 100 lines) to support field troubleshooting without shell access.

### Error handling and UX resilience
- Maintains a rotating log via `logging.handlers.RotatingFileHandler` and displays empathetic, user-friendly error dialog messages when Streamlit exceptions surface. Functions wrap risky operations (file I/O, screenshot capture, cloud sync) with guardrails that surface actionable guidance instead of tracebacks.

### Hotkey integration
- Delegates global keyboard listeners to `kiroshi_hotkeys` to capture clipboard shortcut presses even when the Streamlit window is unfocused. The current case selection toggles which record feeds the hotkey snapshot, allowing quick clipboard fills for build titles, descriptions, and prompts.

### Cloud synchronisation
- Imports `kiroshi_cloud_sync` helpers to validate credentials, manage overlay guidance, decode device tokens, upload/download the AI Educate dataset, and update device status (blocked/allowed). The UI reflects share availability using `cloud_share_status` and emits encrypted payloads through the shared helper layer so both the desktop and cloud clients stay interoperable.

### Chat and AI assistance
- Leverages `kiroshi_chat` for prompt building, memory loading/saving, and system prompt management. The assistant supplies reassurance, detects missing case data (`Verify`), and handles sarcasm mode. Chat settings align with the same AI base URL/mode defaults used by the rest of the app.

## Chat helper module (`kiroshi_chat.py`)
- Provides the shared system prompt, default API routing, and persistence helpers for conversational memory (`kiroshi_memory.json`) and manual references (`manual_memory.json`).
- Exposes `configure_page` for the standalone chat UI, setting the page title/icon safely when invoked directly. Asset paths are computed at import time without calling `st.set_page_config`, preventing duplicate configuration errors when the module is imported by the main app.
- Disables SSL verification warnings to accommodate corporate proxy interception, mirroring the posture taken by the main app for outbound API calls.

## Cloud sync module (`kiroshi_cloud_sync.py`)
- Declares domain-specific exceptions (`CloudError`, `AuthenticationError`, `EncryptionError`, `AgentBlockedError`) to make UI error mapping explicit.
- Calculates and normalises the cloud share root (defaulting to `\\dk-srv-fl-01\CosCare\Nicolas M\KC` or an environment override) and local database roots (`C:/ProgramFiles/KiroshiDatabase` on Windows, `~/KiroshiDatabase` elsewhere).
- Derives Fernet keys from user credentials using PBKDF2 with 390k iterations, encrypts device rosters and AI Educate datasets at rest, and tracks config versions for future migrations.
- Exposes blocking, authentication, dataset summarisation, and overlay guidance utilities that the UI can call synchronously. All filesystem interactions respect a configurable timeout and create intermediate directories as needed.

## Streamlit wrapper (`run_app.py`)
- `_resolve_app_path`: Computes the absolute path to the main application file, handling both source and PyInstaller bundle layouts. It fails loudly with bundling guidance if the app file is missing.
- `_harmonize_security_settings`: Aligns Streamlit CORS and XSRF flags when the `STREAMLIT_SERVER_ENABLE_CORS` environment variable disables CORS, preventing mixed security modes in packaged runs.
- `_set_default_runtime_flags`: Pins default port (`8502`) and disables global dev mode inside frozen bundles so packaged desktops behave predictably.
- `main`: Executes the helper functions above, rewrites `sys.argv`, and delegates to `stcli.main()`.

## How data moves through the system
1. **UI interaction**: User edits or toggles fields within tabs. Each action mutates a shared session state object and triggers autosave of the entire case payload to `autosaves/autosave.json` with a session-specific key.
2. **Hotkey snapshots**: When a case is marked for hotkeys, `kiroshi_hotkeys` receives the latest tables and prompt text, storing them for clipboard access even when the Streamlit window is not focused.
3. **Exports**: On demand, the app generates a PDF (optionally with ReportLab charts) and a ZIP containing attachments, logs, and screenshots. File naming uses the case ID and current date (`TODAY_STR`) to keep bundles deduplicated.
4. **Persistence & reload**: Saving writes the structured case dict to the database directory; loading rehydrates dataclass instances and restores tracking state. Autosave offers immediate recovery if the browser refreshes mid-session.
5. **Cloud exchange**: When cloud sync is enabled, credentials and device tokens are validated via `kiroshi_cloud_sync`. Educate datasets can be uploaded/downloaded through encrypted files in the shared cloud path, while device status analytics are computed on the same dataset store.
6. **Chat integration**: The `Verify` tool inspects the current case data for gaps; chat replies use the system prompt and optional sarcasm mode. Memories and manual docs persist across sessions, giving the assistant continuity.

## Defensive coding patterns to preserve
- Keep all GUI-dependent imports optional and guarded by availability flags; never hard-fail when a desktop environment lacks a display server.
- Avoid calling `st.set_page_config` on import; defer UI-only side effects to execution time to remain compatible with PyInstaller/Streamlit Desktop packaging.
- Preserve the log rotation strategy so field diagnostics remain lightweight and do not grow without bounds.
- Maintain explicit error messages around cloud share availability and encryption failures to help technicians self-service issues without shell access.

## Extension guidelines for AI agents
- Mirror the environment-detection strategy used in `run_app.py` and the main app whenever adding new modules that might be bundled; resolve paths relative to `sys._MEIPASS` when `sys.frozen` is true.
- When adding new tabs or export types, plug into the existing autosave pipeline and update the hotkey snapshot mapping so new data stays reachable from global shortcuts.
- For additional cloud artefacts, reuse the Fernet/PBKDF2 machinery in `kiroshi_cloud_sync` to remain interoperable with existing datasets and avoid version skew.
- Keep chat prompt changes inside `kiroshi_chat.py` so both the main app and any standalone chat interface inherit the same persona and default routing.
