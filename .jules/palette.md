# Palette's Journal

## 2025-01-28 - Standardizing Input Guidance via `auto_text_input`

**Learning:** The application uses a wrapper function `auto_text_input` to handle autosave logic and labeling for text fields. This wrapper correctly propagates `**kwargs` to the underlying Streamlit widget. This makes it trivial to enforce UX consistency (like placeholders) across the entire application without refactoring the state management logic.

**Action:** When adding new text inputs, always use `auto_text_input` instead of raw `st.text_input` to inherit autosave capabilities, and ensure `placeholder` and `help` arguments are provided to guide the user, as the wrapper supports them natively.
