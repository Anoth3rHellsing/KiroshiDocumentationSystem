## 2025-05-15 - [Hardcoded Admin Credentials]
**Vulnerability:** Found hardcoded `admin` / `admin` credentials in the `render_debug_panel` function of `case_documentation_app.py`.
**Learning:** Hardcoded credentials in source code are a common but critical vulnerability, often left over from development or "hidden" features like debug panels.
**Prevention:** Always use environment variables or external configuration for secrets. Use secure comparison functions like `secrets.compare_digest` to prevent timing attacks.
