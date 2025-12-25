## 2025-05-18 - Hardcoded API Keys
**Vulnerability:** Found `sk-proj-...` OpenAI API key hardcoded in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Hardcoded credentials in source code are a critical risk as they can be extracted by anyone with access to the code or build artifacts.
**Prevention:** Always use environment variables for sensitive keys. Defaults in code should be empty or placeholders, never real keys.
