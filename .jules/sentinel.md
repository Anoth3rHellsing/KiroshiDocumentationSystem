## 2026-01-21 - [CRITICAL] Hardcoded OpenAI API Key Removed
**Vulnerability:** A hardcoded OpenAI API key was found in `case_documentation_app.py` and `kiroshi_chat.py`. This key was exposed in the source code.
**Learning:** Hardcoded credentials in source code are a critical risk as they can be extracted by anyone with access to the repository (or the distributed app). Even if intended for internal use, they bypass access controls and revocation mechanisms.
**Prevention:**
1. Always use environment variables for secrets (e.g., `os.environ.get("OPENAI_API_KEY")`).
2. Set default values to empty strings or raise an error if the secret is missing, never fallback to a hardcoded secret.
3. Use secret scanning tools in the CI/CD pipeline to catch these before merge.
