## 2025-05-27 - [Hardcoded OpenAI API Key]
**Vulnerability:** A hardcoded OpenAI API key (`sk-proj-...`) was found in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Even "placeholder" values can sometimes contain real keys during development and accidentally get committed. The code used `os.environ.get(..., "SECRET")`, which makes the secret the default fallback if the environment variable is missing.
**Prevention:** Always use empty strings or clearly invalid placeholders (e.g., `<insert-key>`) for default values. Use `tests/test_no_secrets.py` to scan for key patterns.
