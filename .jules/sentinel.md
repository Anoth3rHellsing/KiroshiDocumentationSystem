## 2026-02-08 - Critical: Hardcoded OpenAI API Key
**Vulnerability:** Hardcoded OpenAI API key (`sk-proj-...`) found in `kiroshi_chat.py` and `case_documentation_app.py` as a default fallback value for `os.environ.get`. This exposed a live credential to anyone with access to the codebase.
**Learning:** The secret was likely added as a convenience for local development or testing to bypass environment configuration, and then propagated via copy-paste.
**Prevention:** Strictly enforce `os.environ` usage without sensitive defaults. Use `.env` files (excluded from version control) for local secrets. Implement pre-commit hooks (e.g., `gitleaks`) to automatically block commits containing high-entropy strings or known key patterns.
