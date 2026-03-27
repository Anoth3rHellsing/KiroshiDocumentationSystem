# Palette's Journal

## 2024-05-22 - Initial Setup
**Learning:** Streamlit apps require different UX strategies than React apps. Standard HTML/CSS tweaks are harder to inject cleanly.
**Action:** Focus on Streamlit's native parameters (like `help=`, `placeholder=`, `on_click=`) and use `st.markdown` carefully for styling.

## 2025-05-22 - Tooltips in Streamlit
**Learning:** Streamlit's `help` parameter is the most robust way to add accessibility context (tooltips) to buttons, as it renders natively and works across themes without custom CSS.
**Action:** Always check `st.button`, `st.text_input`, and `st.popover` for `help=` opportunities before attempting custom HTML injection.

## 2025-05-23 - Empty States in Lists
**Learning:** Iterating directly over lists without checking for emptiness (e.g., `for item in load_items():`) is a common pattern that misses the opportunity for helpful empty states. Users are left wondering if the feature is broken or just empty.
**Action:** Always capture list results into a variable first, check `if not list:` to render an `st.info` or `st.caption` guidance message, and then iterate.

## 2025-05-23 - Destructive Action Confirmation
**Learning:** Destructive actions like "Clear notes" in Streamlit require manual state management for confirmation, as `st.button` doesn't support native confirmation dialogs (unlike `window.confirm` in JS).
**Action:** Use a session state toggle to swap the trigger button with a "Confirm/Cancel" UI within the same container to prevent accidental data loss.
## 2026-03-27 - [Missing confirmation state for destructive actions]
**Learning:** The 'Clear memory' function in kiroshi_chat.py allowed for instant data loss. Destructive UI interactions in this application must use a secondary confirmation state through st.session_state.
**Action:** Implemented an inline confirmation dialog with 'Yes, delete it' and 'Cancel' buttons. When building future destructive actions (like deleting cases or overwriting history), I will apply this same session-state pattern to prevent accidental data loss.
