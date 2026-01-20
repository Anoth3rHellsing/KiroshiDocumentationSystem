## 2025-05-19 - Removed Hardcoded OpenAI API Key
**Vulnerability:** A hardcoded OpenAI API key (`sk-proj-...`) was found in `case_documentation_app.py` and `kiroshi_chat.py`. This is a critical security risk as it exposes the key to anyone with access to the source code.
**Learning:** Hardcoded credentials can easily slip into production code, especially in default configurations or variable definitions intended for testing/development. They remain in git history even if removed, though for this exercise we only focused on the HEAD revision.
**Prevention:**
1.  **Environment Variables:** Always use `os.environ.get()` for sensitive keys.
2.  **Default Values:** Never provide a real secret as a default value. Use `""` or `None`.
3.  **Automated Scanning:** Implemented `tests/test_no_secrets.py` to regex-scan the codebase for `sk-...` patterns during testing, acting as a regression guardrail.
