import os
import re

def test_no_hardcoded_secrets():
    files_to_check = ["case_documentation_app.py", "kiroshi_chat.py"]
    # Pattern for OpenAI API keys (sk-proj- followed by alphanumeric characters)
    # This is a basic pattern to catch the specific leak format we saw
    secret_pattern = re.compile(r'sk-proj-[a-zA-Z0-9_-]+')

    found_secrets = []

    for filename in files_to_check:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                matches = secret_pattern.findall(content)
                if matches:
                    found_secrets.append(f"{filename}: {len(matches)} secret(s) found")

    assert not found_secrets, f"Found hardcoded secrets: {', '.join(found_secrets)}"
