## 2026-02-06 - Hardcoded OpenAI API Key
**Vulnerability:** Found a hardcoded OpenAI API key in `case_documentation_app.py` and `kiroshi_chat.py`. This key was exposed in the source code, potentially allowing unauthorized access to the OpenAI API quota and billing.
**Learning:** Developers might hardcode secrets for convenience during local development or testing and forget to remove them before committing. This highlights the need for vigilance even in quick prototype code.
**Prevention:** Use environment variables or a secure secrets manager to inject credentials at runtime. Implement pre-commit hooks (like `detect-secrets` or `gitleaks`) to scan for high-entropy strings or known key patterns before commits are allowed.
