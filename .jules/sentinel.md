## 2024-05-18 - Hardcoded secret API key in config
**Vulnerability:** A hardcoded OpenAI API key was found in default configurations across `kiroshi_chat.py` and `case_documentation_app.py`.
**Learning:** Default fallbacks must not use sensitive tokens. Environment variable fallbacks for sensitive configurations should default to empty strings or None to ensure tokens are securely provided at runtime instead of being embedded in the source code.
**Prevention:** Use `""` or `None` as the default for configurations relying on environment variables for sensitive tokens.
