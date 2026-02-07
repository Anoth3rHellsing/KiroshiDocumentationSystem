## 2025-05-27 - [Hardcoded API Key]
**Vulnerability:** A hardcoded OpenAI API key was found in `case_documentation_app.py` and `kiroshi_chat.py`.
**Learning:** Even "default" configuration values in public or shared codebases can leak secrets if developers paste their own keys for testing and commit them.
**Prevention:** Use `os.environ.get("KEY", "")` with an empty default. Scan codebase for key patterns (like `sk-proj-`) before committing.
