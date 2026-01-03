## 2025-05-15 - Hardcoded Credentials in Cloud Sync
**Vulnerability:** The `kiroshi_cloud_sync.py` module contained a hardcoded default password (`admin123!`) which was used to initialize the cloud configuration and verify if default credentials were in use. This credential was also documented in the README and displayed in the UI.
**Learning:** Hardcoded credentials, even "default" ones intended for first setup, are a significant risk because users may not change them, leaving installations vulnerable. Relying on a known static hash to detect "default" state is also fragile.
**Prevention:**
1.  Never hardcode passwords or secrets in source code.
2.  Generate secure random credentials during initialization/installation.
3.  Store only hashes, never plaintext, even for generated defaults.
4.  Communicate generated credentials to the user securely (e.g., one-time display in UI or logs) and instruct them to save/change them.
5.  Use state flags (like `uses_default_credentials`) to track security posture rather than comparing against known bad values.
