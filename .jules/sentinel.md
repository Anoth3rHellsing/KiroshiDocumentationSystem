## 2025-10-26 - Hardcoded Default Credentials
**Vulnerability:** Found `DEFAULT_PASSWORD = "admin123!"` hardcoded in `kiroshi_cloud_sync.py`, which was used to initialize the cloud configuration if missing.
**Learning:** Hardcoded default credentials are a major risk even if intended to be changed immediately, as bots scan for them. In desktop apps, "initial setup" flow is often skipped or defaulted, leaving these credentials active.
**Prevention:** Always generate random credentials for initial setup or require the user to set them explicitly via environment variables or interactive setup. Do not embed default passwords in the source code.
