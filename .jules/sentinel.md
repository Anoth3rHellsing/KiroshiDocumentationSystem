## 2025-05-18 - Hardcoded API Key Exposure
**Vulnerability:** A hardcoded OpenAI API key (`sk-proj-uYy...`) was found in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Hardcoded credentials in source code are a common but critical oversight, especially when implementing default fallback values for environment variables.
**Prevention:** Always use empty strings or explicit "dummy" placeholders for default credentials. Implement a pre-commit hook or CI step (like `trufflehog` or `gitleaks`) to scan for secret patterns before code is merged.
