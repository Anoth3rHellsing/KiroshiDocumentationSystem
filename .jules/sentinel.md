## 2026-01-27 - Critical: Hardcoded OpenAI API Key
**Vulnerability:** Found a hardcoded OpenAI API key (`sk-proj-...`) in `case_documentation_app.py` and `kiroshi_chat.py` as a default fallback value. This exposed the key to anyone with access to the codebase.
**Learning:** The key was likely added for convenience during development or testing to avoid setting environment variables, and then forgotten. Hardcoding secrets, even "temporary" ones, is a persistent risk.
**Prevention:** Never hardcode secrets. Use environment variables or a secure vault. Added `tests/test_no_secrets.py` to scan for key patterns in the codebase to prevent regression.
