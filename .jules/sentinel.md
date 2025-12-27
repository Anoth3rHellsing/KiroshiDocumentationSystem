## 2025-05-23 - Hardcoded OpenAI API Keys
**Vulnerability:** Found hardcoded OpenAI API key (`sk-proj-...`) in `case_documentation_app.py` and `kiroshi_chat.py`. The key appeared to be a project-specific key.
**Learning:** Hardcoding secrets as default arguments to `os.environ.get()` is a common antipattern when moving from development to production. It exposes credentials in source control.
**Prevention:**
1. Always use `""` or `None` as the default value for sensitive environment variables.
2. Use the new `tests/test_no_secrets.py` regression test to scan for `sk-` prefixes in key configuration files.
3. Enforce environment variable configuration in `config.json` or `.env` files (excluded from git) rather than fallback strings.
