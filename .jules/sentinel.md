## 2024-05-23 - Hardcoded OpenAI API Key

**Vulnerability:** A valid-looking OpenAI API key (`sk-proj-...`) was hardcoded in `case_documentation_app.py` and `kiroshi_chat.py` as a default value for `DEFAULT_OPENAI_API_KEY`. This exposed the key to anyone with access to the codebase.
**Learning:** Hardcoding "working" credentials as default values for development convenience often leads to accidental commits of secrets. The key was likely used for local testing and then copy-pasted into the default variable.
**Prevention:** Always use `os.environ.get()` with empty strings or explicit placeholders (e.g. `""`) for sensitive defaults. Added `tests/test_no_secrets.py` to scan the codebase for `sk-proj-` patterns to prevent recurrence.
