
## 2024-05-24 - Remove Hardcoded API Keys
**Vulnerability:** Found hardcoded OpenAI API key in case_documentation_app.py and kiroshi_chat.py.
**Learning:** Secrets should never be hardcoded in the codebase, even as fallbacks. They should be loaded exclusively from environment variables or secure credential stores to prevent leakage.
**Prevention:** Rely strictly on `os.environ.get()` with an empty string or None default instead of providing the actual secret inline.
