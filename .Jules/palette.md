## 2026-04-13 - "Clear all" Destructive Action Confirmation
**Learning:** The "Clear all" action on the main Case tab had no confirmation, which is a critical UX flaw that can easily lead to accidental data loss in this environment.
**Action:** Replaced the immediate `clear_case_state` execution with a session-managed confirmation flow using `st.warning` and Confirm/Cancel buttons within the same container.
