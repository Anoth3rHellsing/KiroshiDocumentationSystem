## 2025-05-15 - [Critical Security Findings]
**Vulnerability:** Hardcoded OpenAI API keys were found in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Developers likely added these for convenience during testing or initial setup and forgot to remove them. Relying on `os.environ.get("OPENAI_API_KEY", "actual-secret-key")` is a common but dangerous pattern because the fallback value exposes the secret in the source code.
**Prevention:** Always use `os.environ.get("OPENAI_API_KEY")` without a default value, or with a default value of `""` or `None`. Enforce pre-commit hooks that scan for high-entropy strings or known secret patterns (like `sk-...`).
