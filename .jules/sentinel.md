## 2025-05-24 - Hardcoded OpenAI API Key
**Vulnerability:** A valid OpenAI API key was hardcoded in `case_documentation_app.py` as a fallback value for `DEFAULT_OPENAI_API_KEY`.
**Learning:** Developers likely added this for local testing convenience and forgot to remove it before committing.
**Prevention:** Use `.env` files for local development secrets and ensure they are gitignored. Use pre-commit hooks (like `detect-secrets`) to scan for high-entropy strings or known key patterns.
