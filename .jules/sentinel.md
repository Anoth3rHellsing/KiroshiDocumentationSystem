## 2026-01-26 - Hardcoded OpenAI API Key
**Vulnerability:** Found a hardcoded OpenAI API key (`sk-proj-...`) in both `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Hardcoded secrets often propagate through copy-pasting code or initializing variables with "working" defaults during development and forgetting to remove them.
**Prevention:** Use environment variables for all secrets. Ensure pre-commit hooks or CI/CD pipelines scan for secret patterns (like `sk-`) before merging.
