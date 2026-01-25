import os
import re
import pytest

def test_no_hardcoded_openai_key():
    # Pattern for OpenAI keys: sk-proj- followed by alphanumeric
    # We construct the pattern to avoid self-detection
    prefix = "sk-" + "proj-"

    # Files to ignore
    # .jules is where I write the journal, which might reference the pattern in the description of what I fixed.
    ignore_dirs = [".git", "__pycache__", "node_modules", ".jules", ".pytest_cache"]
    ignore_files = [os.path.basename(__file__), "package-lock.json", "streamlit.log"]

    found_secrets = []

    for root, dirs, files in os.walk("."):
        # filter dirs
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file in ignore_files:
                continue
            # We want to check code and config files
            if not file.endswith((".py", ".json", ".ts", ".js", ".md", ".txt", ".toml")):
                continue

            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if prefix in content:
                        # Double check it's not a false positive (like a comment saying "removed sk-proj-...")
                        # But strictly, we shouldn't even have that in comments if we want to be clean.
                        # However, for this test, existence is enough failure.
                        found_secrets.append(filepath)
            except Exception as e:
                print(f"Could not read {filepath}: {e}")

    assert not found_secrets, f"Found potential OpenAI keys in: {found_secrets}"
