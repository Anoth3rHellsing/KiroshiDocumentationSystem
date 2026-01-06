## 2024-05-23 - [Hardcoded OpenAI Key]
**Vulnerability:** A valid OpenAI API key was hardcoded in `case_documentation_app.py` and `kiroshi_chat.py` as a default value for environment retrieval.
**Learning:** Default values in `os.environ.get()` can be dangerous if they contain secrets, especially when copy-pasting code between local/private projects and public repositories.
**Prevention:** Use empty strings or explicitly raise an error if critical secrets are missing. Never commit "fallback" keys even if they are intended for "internal" builds. Use `.env` files or a dedicated secret manager.
