# Legacy Codebase Analysis: `KiroshiDocumentationSystem-Dev (PRE OPTIMIZATION)/case_documentation_app.py`

This document provides a detailed breakdown of all functions found in the legacy monolithic `case_documentation_app.py` file. It serves as a reference for re-integrating features into the new modular architecture.

## 1. Helper & Utility Functions

### `safe_modal(title: str, key: str | None = None)`
- **Purpose**: Provides a context manager for rendering a modal dialog. It gracefully falls back to `st.container()` if `st.modal` is not available (backwards compatibility).
- **Parameters**: `title` (dialog title), `key` (widget key).

### `_require_reportlab_charts()`
- **Purpose**: Checks if `reportlab` chart components are available. Raises a `RuntimeError` if not, ensuring PDF generation features fail early if dependencies are missing.

### `_collect_recent_logs(max_bytes: int = 65536)`
- **Purpose**: Reads the tail of the application log file (`app.log`) for diagnostic purposes. Used in the Incident Reporter.
- **Parameters**: `max_bytes` (limit of bytes to read from end of file).

### `_ensure_pdf_fonts()`
- **Purpose**: Returns the font names (Regular, Bold) to be used for PDF generation, caching the result. Defaults to "Helvetica".

### `_load_pdf_styles()`
- **Purpose**: Configures and returns a ReportLab stylesheet object (`styles`), along with font names and a special "GhostText" style for hidden text in PDFs.

### `_build_pdf_with_ghost_text(doc, elements, snippets)`
- **Purpose**: Renders a ReportLab PDF document (`doc`) with `elements`. It injects `snippets` as invisible white text behind the content to ensure text extraction/copy-paste works well even for graphical tables.

### `_resolve_configured_attachments_directory()`
- **Purpose**: Resolves the path for storing attachments based on user settings or defaults to `Documents/kiroshi`.

### `_ensure_case_attachments_root()`
- **Purpose**: Ensures the attachments root directory exists. Returns the `Path` and any error encountered.

### `_initialize_storage_paths()`
- **Purpose**: Creates necessary directories (`DATABASE_DIR`, `UTILITIES_DIR`, `TRACKED_CASES_DIR`, etc.) on startup.

### `invoke_gpt(prompt, history, api_key, model, base_url, *, source)`
- **Purpose**: A wrapper around `query_kiroshi` that adds logging for request lifecycle (start/finish/duration) and error handling.
- **Parameters**: Standard AI parameters plus `source` (string label for the caller, e.g., "ai_assist").

### `_shorten_for_log(text, limit)`
- **Purpose**: Truncates text for concise logging.

## 2. Theme & UI Styling

### `ThemePalette` (Dataclass)
- **Purpose**: Defines color schemes (primary, accent, background, etc.).

### `_normalize_hex_color`, `_hex_to_rgb_tuple`, `_blend_hex_colors`, `_rgba`, `_relative_luminance`, `_preferred_text_for_background`
- **Purpose**: Color manipulation helpers for theme generation and contrast calculation.

### `determine_active_theme(today)`
- **Purpose**: Selects the active theme based on settings (dark mode, holiday themes) and the current date (for automatic holiday themes).

### `apply_theme_palette(theme)`
- **Purpose**: Injects CSS variables and global styles into Streamlit based on the selected `ThemePalette`.

### `get_kiroshi_message(theme)`
- **Purpose**: Returns a random "loading message" or quip, optionally flavored by the current theme (e.g., specific messages for "Helldiver" theme).

### `inject_base_styles()`
- **Purpose**: Injects core CSS for the dashboard layout, tutorial badges, and general component styling.

### `render_logo()`
- **Purpose**: Renders the application header, including the logo, version, Kiroshi companion message card, and date.

### `case_loading_overlay(message)`
- **Purpose**: A context manager that displays a full-screen loading overlay with a spinner and cycling "Kiroshi whispers" tips while a long operation runs.

### `streamlit_modal(title, key)`
- **Purpose**: Similar to `safe_modal`, provides a fallback-safe modal context.

### `loading_indicator(message)`
- **Purpose**: A context manager showing `st.spinner`. It enforces a minimum display time to prevent flickering for fast operations.

## 3. Wellness & Cloud Logic

### `_normalize_wellness_settings(raw)`
- **Purpose**: Validates and structures the wellness reminders configuration dict.

### `_time_str_to_time`, `_time_to_string`
- **Purpose**: Converters between `datetime.time` objects and "HH:MM" strings.

### `_calculate_next_wellness_event(settings, now)`
- **Purpose**: Determines the next scheduled break or lunch time based on current settings.

### `_format_timedelta_compact(delta)`
- **Purpose**: Formats a `timedelta` into a short string like "1h 30m" or "moments".

### `_calculate_lunch_midpoint`
- **Purpose**: Calculates the midpoint of the lunch break for scheduling midday sync tasks.

### `_resolve_automation_cloud_credentials()`
- **Purpose**: Retrieves cloud credentials from session state or secrets.

### `_perform_midday_cloud_refresh(now)`
- **Purpose**: Executes the logic to regenerate the AI Educate dataset and upload it to Kiroshi Cloud if conditions are met.

### `_maybe_trigger_midday_cloud_refresh(now)`
- **Purpose**: Checks if it's time to run the midday cloud refresh and triggers it if so.

### `_refresh_wellness_reminder_state(now)`
- **Purpose**: Updates session state with the current status of wellness reminders (next event, whether to show alert).

### `_ensure_wellness_alert_styles()`
- **Purpose**: Injects CSS specific to the wellness alert banner.

### `_get_wellness_audio_clip()`
- **Purpose**: Generates or retrieves a cached audio beep for wellness alerts.

### `_update_wellness_alert_state`, `_dismiss_wellness_alert`, `_start_wellness_pause`, `_complete_wellness_pause`, `_return_to_wellness_alert`
- **Purpose**: State transition functions for the wellness reminder UI flow.

### `render_wellness_alert(reminder_state)`
- **Purpose**: Renders the wellness reminder banner or modal overlay based on the current state.

## 4. Initialization & Updates

### `_load_persistent_settings()`, `_persist_setting(key)`
- **Purpose**: Reads/writes the `settings.json` file.

### `_get_persistent_default(key, fallback)`
- **Purpose**: Helper to retrieve a setting value with a fallback.

### `check_for_updates()`
- **Purpose**: Queries GitHub API to check for a newer version of the application. Returns `UpdateCheckResult`.

### `apply_github_update(repo, branch)`
- **Purpose**: Downloads the source zip from GitHub, extracts it, and updates the local application files.

### `_discover_default_branch`, `_resolve_update_target`, `_get_update_token`, `_build_github_headers`
- **Purpose**: Helpers for GitHub API interactions (finding branch, auth headers).

## 5. Tutorial System

### `render_onboarding_tutorial()`
- **Purpose**: Renders the interactive onboarding tutorial wizard if enabled. Manages steps, visuals, and completion logic.

### `_mark_tutorial_completion(status)`
- **Purpose**: Updates metadata when the user finishes or skips the tutorial.

### `_render_tutorial_visual(kind)`
- **Purpose**: Renders specific visual aids (tables, cards, mockups) for different tutorial steps.

## 6. Case Management & Data

### `CaseData` (Dataclass), `TrackingData` (Dataclass), `CaseSession` (Dataclass)
- **Purpose**: Data models representing the case state, tracking info, and UI session state.

### `save_case_to_database(case, ...)`
- **Purpose**: Serializes `CaseData` to a JSON file in `DATABASE_DIR`. Handles attachments persistence and history updates.

### `load_case_from_path(path)`, `load_case_from_bytes(data)`
- **Purpose**: Loads a case JSON into the active session state. Handles attachment hydration.

### `autosave()`, `autosave_payload()`
- **Purpose**: Periodically persists the current case state to a temporary file in `autosaves/`.

### `persist_case_attachments(case_id)`
- **Purpose**: Writes in-memory attachment buffers (uploads, screenshots) to disk under `CASE_ATTACHMENTS_ROOT`.

### `load_case_attachments(case_id, attachments_data)`
- **Purpose**: Reads attachments from disk back into memory buffers for the UI.

### `load_recent_cases()`, `update_recent_cases(case_id, path)`
- **Purpose**: Manages the `recent_cases.json` list of recently accessed files.

### `load_tracked_cases()`
- **Purpose**: Scans `DATABASE_DIR` and legacy `TRACKED_CASES_DIR` for cases with `tracking.active = True`. Returns a list of summaries.

### `update_tracked_priority`, `update_tracked_status`, `untrack_case`
- **Purpose**: Functions to modify specific fields of a saved case JSON without full load, used by dashboard quick actions.

### `list_saved_cases()`
- **Purpose**: Lists all JSON files in `DATABASE_DIR` for the "Saved Cases" view.

## 7. AI & Text Processing

### `_extract_keywords(*texts)`
- **Purpose**: simple keyword extraction from text fields.

### `_summarize_text(text, width)`
- **Purpose**: Truncates text.

### `build_ai_learning_dataset()`, `ensure_ai_learning_dataset()`
- **Purpose**: Scans all saved cases to build an aggregate `AILearning.json` dataset for the "Educate" feature.

### `find_relevant_learning_cases(case, dataset)`
- **Purpose**: Searches the AI dataset for cases similar to the current one based on keywords and metadata.

### `run_bug_detector(dataset)`
- **Purpose**: Analyzes the dataset for recurring patterns and bug mentions.

### `collect_ai_educate_report_data(dataset)`
- **Purpose**: Aggregates statistics (counts, timelines) from the dataset for the Report view.

### `parse_categorizer_summary(text)`
- **Purpose**: Parses the text output from the AI Categorizer into structured fields (Product, Topic, etc.).

## 8. Rendering Views

### `render_dashboard()`
- **Purpose**: Renders the main dashboard tab (tracked cases, recent files, wellness banner).

### `render_tracked_cases_dashboard(cases)`
- **Purpose**: Renders the table of tracked cases with filters and action buttons.

### `render_saved_cases_page()`
- **Purpose**: Renders the "Saved Cases" tab with filtering and export options.

### `render_settings_panel()`
- **Purpose**: Renders the Settings tab (appearance, AI config, cloud, updates).

### `render_report_panel()`
- **Purpose**: Renders the AI Educate Report tab (stats, charts, PDF export).

### `render_case_ui(case_idx)`
- **Purpose**: The main orchestrator for a Case Tab. Renders sub-tabs (Case, Tracking, Escalations, Email, etc.) for a specific case session.

### `render_case_kiroshi_chat_panel(case_idx)`
- **Purpose**: Renders the contextual chat interface within a case tab.

### `render_autohotkey_panel`
- **Purpose**: Renders the UI for generating/downloading AutoHotkey scripts.

## 9. PDF Generation

### `make_pdf(d, cat_map)`, `make_tables_pdf(d)`
- **Purpose**: Generates PDF summaries of case data.

### `build_incident_report_pdf(...)`
- **Purpose**: Generates a PDF for the Incident Reporter (logs + context).

### `generate_ai_educate_report_pdf(insights)`
- **Purpose**: Generates a PDF report of the AI Educate analytics.

### `generate_recurring_issue_pdf(pattern_entry)`
- **Purpose**: Generates a PDF guide for a specific recurring issue pattern.

## 10. Email & Text Generation

### `build_email_intro(d)`
- **Purpose**: Generates the standard email opening.

### `build_third_line_escalation(d)`
- **Purpose**: Generates the 3Q escalation template.

### `build_dell_escalation_email(d)`
- **Purpose**: Generates the Dell escalation email body.

### `build_autohotkey_script(cases, cat_map)`
- **Purpose**: Generates the AHK script content for quick pasting.

## 11. Screenshot & Hotkeys

### `render_screenshot_capture_footer`
- **Purpose**: Renders the sticky footer for screenshot controls.

### `_capture_screenshot_from_ui`
- **Purpose**: Trigger for the capture logic.

### `_refresh_hotkey_snapshot`
- **Purpose**: Updates the global hotkey state (clipboard targets) based on the active case.

## 12. Legacy/Unused or Niche

### `doom_game.py` / `tab_bored`
- **Purpose**: The "I'm bored" game logic.

### `_migrate_hardware_test_state`
- **Purpose**: One-time migration for legacy boolean hardware flags to text.
