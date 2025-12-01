# Kiroshi Documentation System: Refactoring Plan

## Objective
Deconstruct the 19k+ line `case_documentation_app.py` monolith into a maintainable, modular Python package (`KiroshiApp`) without breaking existing functionality or state management.

## Phase 1: Foundation & Data Models (Low Risk)
*   **Goal:** Extract pure data structures and core logic.
*   **Steps:**
    1.  Create package structure `KiroshiApp/`.
    2.  Create `KiroshiApp/models.py`:
        *   Move `CaseData`, `TrackingData`, `RemoteSessionEntry`, `MilestoneProgressState`, `CaseMilestoneState`, `CaseSession`.
    3.  Create `KiroshiApp/constants.py`:
        *   Move `VERSION`, `DEFAULT_OPENAI_API_KEY` (deprecated), `PRIORITY_OPTIONS`, `CASE_TAB_SLUGS`, etc.
    4.  Update `case_documentation_app.py` to import from these new modules.

## Phase 2: Utilities & Services (Medium Risk)
*   **Goal:** Extract business logic and helper functions.
*   **Steps:**
    1.  Create `KiroshiApp/utils.py`:
        *   Move string helpers: `sanitize_filename`, `_summarize_text`, `_extract_keywords`.
        *   Move date helpers: `_utc_now_z`, `_parse_utc_timestamp`.
    2.  Create `KiroshiApp/services/`:
        *   `screenshots.py`: Move `ScreenshotAsset`, `ScreenshotService`, `_generate_screenshot_basename`.
        *   `autosave.py`: Move `autosave`, `load_autosave`, and related hashing logic.
    3.  Update imports in the main file.

## Phase 3: UI Component Extraction (High Risk)
*   **Goal:** Break down the `render_case_ui` giant function.
*   **Challenge:** These functions rely heavily on `st.session_state` and global variables (`D`, `cat_map`).
*   **Strategy:** Pass state explicitly or use a context object.
*   **Steps:**
    1.  Create `KiroshiApp/ui/`:
        *   `dashboard.py`: `render_dashboard`, `render_tracked_cases_dashboard`.
        *   `case_tabs/`:
            *   `header.py`: `render_case_header_section`.
            *   `email.py`: Logic for the Email Prompt Generator tab.
            *   `tracking.py`: Logic for the Tracking tab.
            *   `remote.py`: Logic for the Remote Session tab.
    2.  Refactor `case_documentation_app.py` to act as a coordinator that calls these render functions.

## Phase 4: Entry Point & Configuration
*   **Goal:** A clean entry point that initializes the app.
*   **Steps:**
    1.  Create `KiroshiApp/main.py` as the new entry point.
    2.  Ensure `run_app.py` points to the new location.

## Compatibility Note
*   **Streamlit State:** Refactoring must preserve the session state keys used by widgets. We will keep the `widget_key` and `_register_widget_key` logic in a shared utility module (`KiroshiApp/state_management.py`) to ensure ID stability.
