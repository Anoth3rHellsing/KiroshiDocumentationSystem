# Sentinel Journal

## 2024-05-23 - [Hardcoded Credentials in Configuration]
**Vulnerability:** Found hardcoded `DEFAULT_PASSWORD` in `kiroshi_cloud_sync.py` used to initialize default cloud configuration.
**Learning:** Default configurations should never include hardcoded secrets, even for convenience. Code that relies on "default" passwords creates a permanent risk window until the user rotates them.
**Prevention:** Implement a "setup required" state (like `CloudSetupRequiredError`) that forces user input for secrets before the application can function, rather than falling back to defaults.
