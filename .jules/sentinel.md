## 2025-05-15 - Hardcoded Admin Credentials
**Vulnerability:** Found hardcoded "admin"/"admin" credentials in `case_documentation_app.py` for a debug panel.
**Learning:** Hardcoded credentials are often left in "debug" or "internal" features that are assumed to be safe or temporary.
**Prevention:** Always use environment variables for authentication, even for debug features. Enforce secrets scanning that looks for simple patterns like "admin"/"password" in addition to API key patterns.
