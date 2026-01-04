## 2025-05-19 - Hardcoded Secrets
**Vulnerability:** Hardcoded OpenAI API key (`sk-proj-...`) found in `case_documentation_app.py` and `kiroshi_chat.py` as a fallback default value.
**Learning:** Developers likely added this for convenience or local testing and forgot to remove it before committing. Even if it's a "test" key, it follows the production key format and risks leakage if the repo becomes public or shared.
**Prevention:**
1. Always use environment variables for secrets.
2. Use pre-commit hooks (like `detect-secrets` or `trufflehog`) to scan for secret patterns.
3. Ensure default values for sensitive configuration are empty, `None`, or explicitly non-functional placeholders (e.g., `<API_KEY_HERE>`).
