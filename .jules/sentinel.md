## 2024-05-24 - [CRITICAL] Hardcoded Secrets and Secure Initialization
**Vulnerability:** Found hardcoded `DEFAULT_PASSWORD = "admin123!"` in `kiroshi_cloud_sync.py`, used to initialize new cloud configurations. This meant every default installation shared the same administrative password.
**Learning:** Hardcoded defaults for "convenience" often become permanent vulnerabilities because users rarely rotate them immediately. The original code even printed this password to the UI, training users to rely on it.
**Prevention:**
1. Removed `DEFAULT_PASSWORD` constant entirely (renamed to `LEGACY_DEFAULT_PASSWORD` only for backward compatibility checks).
2. Implemented dynamic secure password generation using `secrets.choice` for new installs.
3. Added support for `KIROSHI_INITIAL_ADMIN_PASSWORD` env var for automated/headless setups.
4. Changed UI to instruct checking server logs (`stderr`) instead of displaying credentials, enforcing a "secure by default" posture where physical/shell access is required to get the initial secret.
