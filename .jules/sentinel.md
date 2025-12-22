## 2025-05-19 - Hardcoded OpenAI API Key
**Vulnerability:** A valid OpenAI API key was found hardcoded in `case_documentation_app.py` and `kiroshi_chat.py`. This key started with `sk-proj-` and was exposed in the source code as a default fallback.
**Learning:** Developers might hardcode secrets during development for convenience or debugging and forget to remove them before committing. The presence of it as a default argument in `os.environ.get(..., "SECRET")` is a common anti-pattern.
**Prevention:**
1. Use pre-commit hooks (like `detect-secrets` or `gitleaks`) to scan for secrets before commit.
2. Never provide a secret string as the default value for environment variable lookups. Use `None` or an empty string, and handle the missing case gracefully at runtime.
