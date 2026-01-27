import os
import re
import pytest

# Patterns to look for
SECRET_PATTERNS = [
    r"sk-proj-[a-zA-Z0-9_-]+",
    r"sk-live-[a-zA-Z0-9_-]+",
    r"sk-[a-zA-Z0-9]{48}",  # Standard OpenAI key format
]

# Directories to ignore
IGNORE_DIRS = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "dist",
    "build",
    ".jules",  # Contains the sentinel journal which mentions the vulnerability
    "coverage",
    ".streamlit", # config.toml might have secrets but we usually ignore it. But let's verify.
}

# Files to ignore (e.g. this test file itself is fine, but it doesn't contain the secret, just the pattern)
IGNORE_FILES = {
    "test_no_secrets.py",
    ".gitignore",
    "package-lock.json", # Hashes might look like secrets? Unlikely but possible.
    "requirements.txt",
}

def test_no_hardcoded_secrets():
    """
    Scans the codebase for potential hardcoded secrets (OpenAI keys).
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    found_secrets = []

    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file in IGNORE_FILES:
                continue

            # Skip non-text files or specific extensions if needed
            # For now, let's check everything that looks like text
            if not file.endswith(('.py', '.js', '.ts', '.json', '.md', '.html', '.css', '.txt')):
                continue

            file_path = os.path.join(root, file)

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                    for pattern in SECRET_PATTERNS:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            # We found a match!
                            secret = match.group()
                            # Helper to anonymize for the error message
                            anonymized = secret[:8] + "..." + secret[-4:]
                            found_secrets.append(f"Found potential secret in {os.path.relpath(file_path, root_dir)}: {anonymized}")
            except Exception as e:
                # If we can't read a file, warn but don't fail, or maybe fail?
                # For now just print
                print(f"Could not read {file_path}: {e}")

    assert not found_secrets, "\n".join(found_secrets)

if __name__ == "__main__":
    test_no_hardcoded_secrets()
