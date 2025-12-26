import os
from pathlib import Path

def test_no_hardcoded_openai_key():
    app_file = Path("case_documentation_app.py")
    if not app_file.exists():
        # Maybe we are in tests/
        app_file = Path("../case_documentation_app.py")

    content = app_file.read_text(encoding="utf-8")

    # Check for the key pattern start, rather than the full key
    # or ensure the specific line is correct.

    # We want to ensure we don't find the specific signature of the old key
    # but we can't put the old key here.

    # Instead, we can verify that the DEFAULT_OPENAI_API_KEY definition
    # looks like the safe version.

    safe_definition = 'DEFAULT_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")'

    if safe_definition not in content:
         # It might be formatted differently, so let's check negative condition
         # We check for a long string starting with sk-proj which indicates a hardcoded key
         import re
         # Matches sk-proj- followed by at least 20 chars
         match = re.search(r'sk-proj-[a-zA-Z0-9_-]{20,}', content)
         if match:
             raise AssertionError(f"Found potential hardcoded OpenAI API key: {match.group(0)[:15]}...")

if __name__ == "__main__":
    try:
        test_no_hardcoded_openai_key()
    except AssertionError as e:
        print(f"Test FAILED: {e}")
        exit(1)
