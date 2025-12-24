## 2024-05-24 - Hardcoded Secrets in Source Code
**Vulnerability:** A hardcoded OpenAI API key was found in `case_documentation_app.py` as a default value for the `OPENAI_API_KEY` environment variable.
**Learning:** Default values in code, especially for secrets, can easily be committed to version control and exposed. Developers often put "fallback" keys for convenience during testing, but this practice is dangerous.
**Prevention:**
1.  Never assign hardcoded secrets as default values in code.
2.  Use environment variables exclusively for secrets.
3.  Implement pre-commit hooks (like `git-secrets` or `trufflehog`) to scan for secret patterns before committing.
4.  If a default is needed for local development, load it from a `.env` file that is gitignored, not from the source code itself.
