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
## 2024-04-06 - Destructive Action Confirmations
**Learning:** Destructive actions in Streamlit (like resetting a workspace) require a confirmation dialog to prevent accidental data loss. This can be implemented elegantly without custom components by using `st.session_state` to track confirmation state, swapping the primary button with Confirm/Cancel buttons in a single container.
**Action:** Always implement a two-step `st.session_state` confirmation flow for any button that permanently deletes data or resets application state.
