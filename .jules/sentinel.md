## 2024-05-23 - Hardcoded Credentials in Cloud Sync
**Vulnerability:** The `kiroshi_cloud_sync` module used a hardcoded default password ("admin123!") for new cloud configurations, which was also exposed in the `kiroshi_cloud_client` UI.
**Learning:** Hardcoded defaults in "library" code can be pervasive. Even if the UI intends to warn users, the underlying initialization logic often propagates the insecurity. Backward compatibility (handling existing "legacy" defaults vs new "secure" defaults) complicates the fix.
**Prevention:** Use `secrets.token_urlsafe()` or similar CSPRNGs to generate initial credentials at runtime. Avoid `DEFAULT_PASSWORD` constants in source code.
