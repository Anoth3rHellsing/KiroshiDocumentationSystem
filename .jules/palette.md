## 2025-05-15 - Streamlit Button Tooltips and Playwright

**Learning:** Adding the `help` argument to `st.button` in Streamlit causes it to render duplicate DOM elements containing the button label (one for the button, one for the tooltip container/aria). This causes Playwright strict-mode selectors like `get_by_text("Label")` to fail with a "strict mode violation" because it finds multiple elements with that text.

**Action:** When adding tooltips to buttons in Streamlit apps that are covered by Playwright tests:
1.  Verify if the test uses `get_by_text`.
2.  If so, update the test selector to be more specific (e.g., `get_by_role('button', name='Label')` or `.first()`).
