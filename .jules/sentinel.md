## 2025-02-27 - Remove hardcoded debug credentials and prevent timing attacks
**Vulnerability:** Hardcoded "admin"/"admin" credentials existed in the debug panel authentication check. Additionally, standard string comparison (`==`) was used, leaving the component vulnerable to timing attacks.
**Learning:** Hardcoded credentials are a critical security risk as they bypass normal authentication flows and cannot be rotated without code changes. Standard string comparison can reveal credential length and characters through timing differences.
**Prevention:** Rely on environment variables (e.g., `KIROSHI_DEBUG_USER` and `KIROSHI_DEBUG_PASSWORD`) to inject credentials. Use `secrets.compare_digest` for constant-time comparison to thwart timing attacks.
