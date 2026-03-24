
## 2025-05-20 - Hardcoded API Key Leak
**Vulnerability:** Default OpenAI API keys were hardcoded into application source files (`case_documentation_app.py` and `kiroshi_chat.py`), creating a critical risk of credential exposure if the source code was shared or committed publicly.
**Learning:** Developers relied on hardcoded fallback defaults for `os.environ.get()` instead of secure defaults or empty strings, meaning the application shipped with valid credentials embedded in plain text.
**Prevention:** Never include sensitive tokens, passwords, or API keys directly in source code. Use environment variables securely and default them to empty strings `""` or safe placeholders, relying on documentation or initialization scripts to prompt the user to configure their own keys safely.
