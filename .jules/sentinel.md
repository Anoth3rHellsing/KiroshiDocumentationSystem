## 2025-05-19 - Hardcoded API Keys and Weak Debug Credentials

**Vulnerability:** Found `DEFAULT_OPENAI_API_KEY` hardcoded with a specific "sk-proj-..." value in `case_documentation_app.py` and `kiroshi_chat.py`. Also found a hardcoded debug panel login `user="admin" and pw="admin"`.

**Learning:** These likely originated from a developer hardcoding their personal or project key for convenience during testing and forgetting to remove it before commit. The debug credentials were likely a placeholder.

**Prevention:**
1.  Always use `os.environ.get("KEY", "")` with an empty default for secrets.
2.  Use a pre-commit hook (like `detect-secrets` or `trufflehog`) to scan for high-entropy strings or known key patterns.
3.  For debug panels, rely on environment variables or a proper authentication system, never hardcoded strings in the source.
