import os
import sys

def test_no_hardcoded_keys():
    """Verify that DEFAULT_OPENAI_API_KEY does not contain a hardcoded key."""

    # Check case_documentation_app.py
    with open("case_documentation_app.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Look for the specific variable assignment
    if 'DEFAULT_OPENAI_API_KEY = os.environ.get(' in content:
        # Extract the line(s)
        import re
        match = re.search(r'DEFAULT_OPENAI_API_KEY = os.environ.get\(\s*"OPENAI_API_KEY",\s*"(sk-[^"]+)"', content, re.DOTALL)
        if match:
            print("❌ FAILURE: Hardcoded OpenAI API key found in case_documentation_app.py")
            sys.exit(1)

    # Check kiroshi_chat.py
    with open("kiroshi_chat.py", "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r'DEFAULT_OPENAI_API_KEY = os.environ.get\(\s*"OPENAI_API_KEY",\s*"(sk-[^"]+)"', content, re.DOTALL)
    if match:
        print("❌ FAILURE: Hardcoded OpenAI API key found in kiroshi_chat.py")
        sys.exit(1)

    print("✅ SUCCESS: No hardcoded OpenAI API keys found in checked files.")

if __name__ == "__main__":
    test_no_hardcoded_keys()
