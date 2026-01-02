## 2025-05-23 - Hardcoded Credentials Pattern
**Vulnerability:** A hardcoded API key (OpenAI) was found directly assigned to a default configuration variable in multiple files.
**Learning:** The hardcoded value was likely a leftover from development or testing that was copy-pasted across modules. The pattern `DEFAULT_... = os.environ.get(..., 'hardcoded_value')` is a common source of leaks because it provides a fallback that shouldn't exist in production code.
**Prevention:**
1.  **Never provide sensitive fallbacks:** Use `os.environ.get('KEY', '')` (empty string) or raise an error if the key is missing.
2.  **Linting:** Use tools like `gitleaks` or `trufflehog` in pre-commit hooks to scan for high-entropy strings or known key patterns.
3.  **Code Review:** Specifically check any `os.environ.get` call during review to ensure the second argument is safe.