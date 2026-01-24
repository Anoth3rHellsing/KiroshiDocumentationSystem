## 2026-01-24 - [Hardcoded Credentials in Debug Panel]
**Vulnerability:** Found hardcoded `admin` / `admin` credentials in `case_documentation_app.py` protecting the debug panel.
**Learning:** Hardcoded credentials for "internal" or "debug" features are often overlooked but present a significant risk if the application is exposed.
**Prevention:** Always use environment variables or a secure configuration store for credentials, even for debug features. Default credentials should trigger a warning.
