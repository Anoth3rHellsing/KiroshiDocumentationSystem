## 2024-10-25 - Hardcoded API Key and XSS Risks
**Vulnerability:** Found a hardcoded OpenAI API key in `case_documentation_app.py` (`DEFAULT_OPENAI_API_KEY`). Also identified potential XSS in `components.html` usage where user input is injected into `<script>` blocks via `json.dumps()` without HTML escaping, specifically in `build_third_line_escalation`.
**Learning:** `json.dumps()` is safe for JavaScript string contexts but NOT for HTML script contexts because it doesn't escape `</script>`. Browsers parse the HTML tag structure before executing JS.
**Prevention:** Always use environment variables for secrets. For script injection, use a robust sanitizer or `base64` encoding to transfer data to the frontend, or ensure `</` is escaped to `<\/`.
