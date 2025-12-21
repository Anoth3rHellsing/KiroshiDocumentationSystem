## 2024-05-23 - Hardcoded Production Secrets
**Vulnerability:** Found a hardcoded OpenAI production API key (`sk-proj-...`) in `case_documentation_app.py` and `kiroshi_chat.py` as a fallback default value.
**Learning:** Fallback values for sensitive configuration should never be real secrets, even in development. The assumption that environment variables will always be present led to "convenience" fallbacks that leaked credentials.
**Prevention:**
1. Use empty strings or explicitly invalid placeholders (e.g., `""` or `"<missing>"`) for default secrets.
2. Implement pre-commit hooks (like `detect-secrets` or `gitleaks`) to scan for high-entropy strings or known key patterns before commit.
