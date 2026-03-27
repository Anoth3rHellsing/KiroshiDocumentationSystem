## 2025-03-27 - Remove hardcoded debug panel backdoor
**Vulnerability:** A hardcoded plaintext password ('admin') was used as a backdoor for the application's debug panel, posing a significant security risk.
**Learning:** Hardcoded credentials allow unauthorized access to sensitive application functionality (debug logs, configuration, telemetry) without any chance of password rotation. It also bypasses standard authentication checks.
**Prevention:** Always use environment variables, secure secret managers, or salted hashed configurations instead of plaintext hardcoded passwords, and use timing-safe comparison functions (e.g., `secrets.compare_digest`) when authenticating against them.
