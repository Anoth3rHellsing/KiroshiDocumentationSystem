## 2024-10-15 - Hardcoded OpenAI API Key
**Vulnerability:** A valid OpenAI API key was hardcoded in `case_documentation_app.py` and `kiroshi_chat.py` as a fallback default value for `DEFAULT_OPENAI_API_KEY`.
**Learning:** Developers likely added this for convenience during local testing or to ensure the app worked out-of-the-box without configuration, overlooking the risk of committing it to version control.
**Prevention:** Always use environment variables for secrets. Set default values to empty strings or `None`. Use tools like `git-secrets` or pre-commit hooks to scan for high-entropy strings or known key patterns before committing.
