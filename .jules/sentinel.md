## 2025-05-17 - Hardcoded API Key Exposure
**Vulnerability:** A valid-looking OpenAI API key (`sk-proj-...`) was hardcoded as a default value in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Developers likely added this for convenience during local testing or to ensure the app worked "out of the box" without configuration, but failed to remove it before committing.
**Prevention:**
1.  Never commit secrets. Use `.env` files or environment variables.
2.  Use tools like `git-secrets` or pre-commit hooks to scan for API key patterns.
3.  If a default is needed for testing, use a mock or a placeholder that is clearly invalid (e.g., `sk-placeholder...`).
