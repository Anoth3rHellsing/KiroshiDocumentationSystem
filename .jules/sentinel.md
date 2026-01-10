## 2026-01-10 - [CRITICAL] Hardcoded OpenAI API Key Found in Source Code

**Vulnerability:**
Detected a valid-looking OpenAI API key (`sk-proj-...`) hardcoded as a default value for `DEFAULT_OPENAI_API_KEY` in both `kiroshi_chat.py` and `case_documentation_app.py`.

**Learning:**
Developers likely added this for local convenience or testing and forgot to remove it before committing. The use of `os.environ.get("KEY", "fallback_secret")` is a common anti-pattern that exposes secrets if the environment variable is missing.

**Prevention:**
- Enforce strict checks against hardcoded secrets using pre-commit hooks or CI/CD scanners (e.g., git-secrets, talisman).
- Refactor code to fail securely (raise an error or disable features) if required secrets are missing, rather than falling back to an insecure default.
- Added `tests/test_no_secrets.py` to perform static analysis (AST) on source files to catch specific patterns of hardcoded keys in future builds.
