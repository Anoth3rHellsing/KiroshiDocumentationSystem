## 2026-01-23 - Hardcoded Secrets in Default Configuration

**Vulnerability:** Found hardcoded OpenAI API keys (`sk-proj-...`) assigned as default values for `DEFAULT_OPENAI_API_KEY` in `case_documentation_app.py` and `kiroshi_chat.py`. While they might be placeholders or revoked keys, their presence in source code poses a high risk of leakage if they are valid or if developers copy the pattern with valid keys.

**Learning:** The keys were likely added as a convenience for development or testing but were not removed before committing. The use of `os.environ.get(..., "HARDCODED_KEY")` is a dangerous pattern that prioritizes convenience over security.

**Prevention:** Always use empty strings or `None` as default values for sensitive configuration variables. Enforce pre-commit hooks that scan for secret patterns (regex for `sk-[a-zA-Z0-9]{48}`) to prevent accidental commits.
