
## 2026-01-11 - Removed Hardcoded OpenAI API Key

**Vulnerability:** A live OpenAI API key (`sk-proj-...`) was hardcoded in `case_documentation_app.py` and `kiroshi_chat.py` as a fallback value for `DEFAULT_OPENAI_API_KEY`.
**Learning:** Hardcoding secrets as fallbacks, even for development convenience, risks leaking them if the codebase is shared or exposed. The key was visible in plain text.
**Prevention:** Always use environment variables for secrets. Use empty strings or placeholders for default values. Implement pre-commit hooks or CI checks to scan for secret patterns (like `sk-`) before merging.
