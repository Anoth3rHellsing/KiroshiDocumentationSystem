## 2026-02-04 - [CRITICAL] Hardcoded Debug Credentials
**Vulnerability:** The debug panel in `case_documentation_app.py` used hardcoded string literals ("admin"/"admin") for authentication.
**Learning:** Hardcoded credentials in source code are a high risk as they are exposed to anyone with code access and cannot be rotated without code changes. Even "internal" tools can be a pivot point if exposed.
**Prevention:** Always use environment variables for sensitive credentials. Use `secrets.compare_digest` for password comparisons to prevent timing attacks.
