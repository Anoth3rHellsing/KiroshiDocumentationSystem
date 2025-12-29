## 2025-05-18 - Hardcoded API Key Exposure
**Vulnerability:** A valid OpenAI API key (`sk-proj-...`) was hardcoded directly in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Hardcoded secrets often slip in during rapid prototyping when developers want to "just make it work" without setting up environment variables.
**Prevention:** Use `os.environ.get()` with safe defaults (empty string) from day one. Implement a pre-commit hook (like `detect-secrets` or `trufflehog`) or a CI test (like `tests/test_no_secrets.py`) to catch high-entropy strings before they hit the codebase.

## 2025-05-18 - SSL Verification Bypass
**Vulnerability:** SSL verification is globally disabled via `urllib3.disable_warnings` and `verify=False` in requests.
**Learning:** This is a deliberate architectural choice to support operation within a specific corporate network environment that uses SSL interception proxies (Man-in-the-Middle for inspection).
**Prevention:** While this cannot be "fixed" without breaking the app in its target environment, it should be scoped as narrowly as possible (e.g., only for specific trusted domains) rather than globally disabled, if future architecture allows.
