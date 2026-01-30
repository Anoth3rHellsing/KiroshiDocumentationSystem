import os
import re
import unittest

class TestNoSecrets(unittest.TestCase):
    def test_no_exposed_api_keys(self):
        """Scans the codebase for potential OpenAI API keys."""
        # Simple regex for sk- followed by at least 20 alphanumeric chars
        # This avoids matching short placeholders like 'sk-key'
        secret_pattern = re.compile(r"sk-[a-zA-Z0-9-_]{20,}")

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        exclude_dirs = {
            ".git",
            ".jules",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
            "venv",
            ".venv",
            "dist",
            "build"
        }

        exclude_files = {
            "config.example.json",
            "test_no_secrets.py", # Exclude self
            "package-lock.json",
        }

        found_secrets = []

        for root, dirs, files in os.walk(repo_root):
            # Modify dirs in-place to skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file in exclude_files:
                    continue

                # Only check relevant extensions
                if not file.endswith(('.py', '.json', '.js', '.ts', '.md', '.txt', '.yml', '.yaml')):
                    continue

                filepath = os.path.join(root, file)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        matches = secret_pattern.findall(content)
                        for match in matches:
                            # Double check if it's the test file itself (if path logic failed)
                            if "test_no_secrets.py" in filepath:
                                continue
                            found_secrets.append(f"{filepath}: {match[:10]}...")
                except Exception as e:
                    print(f"Could not read {filepath}: {e}")

        if found_secrets:
            self.fail(f"Found potential API keys in the following files:\n" + "\n".join(found_secrets))

if __name__ == "__main__":
    unittest.main()
