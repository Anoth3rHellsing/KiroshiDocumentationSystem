## 2025-05-19 - Hardcoded OpenAI API Key
**Vulnerability:** A live OpenAI API key was hardcoded in `case_documentation_app.py` and `kiroshi_chat.py` as a fallback default.
**Learning:** Default arguments in `os.environ.get()` are a common place where secrets leak during development convenience.
**Prevention:** Use empty strings for defaults and enforce configuration via environment variables or secure storage only.
