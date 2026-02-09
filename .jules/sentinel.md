## 2026-02-09 - Insecure Update Mechanism

**Vulnerability:** The application update mechanism (and other HTTP requests) disabled SSL certificate verification (`verify=False`) by default, exposing users to Man-in-the-Middle (MITM) attacks where malicious updates could be injected.
**Learning:** Hardcoding insecure defaults to support legacy corporate environments (interception proxies) puts all users at risk. Security should be opt-out, not opt-in.
**Prevention:** Introduced `VERIFY_SSL` toggle (defaulting to True) that respects the system trust store. Corporate environments must now explicitly set `KIROSHI_INSECURE_SKIP_VERIFY=true` or install their CA certificates properly.
