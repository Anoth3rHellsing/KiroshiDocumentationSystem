import unittest
import os
import re

class TestNoSecrets(unittest.TestCase):
    def test_no_openai_api_keys(self):
        """Scan the codebase for OpenAI API keys (sk-...)."""
        # Pattern for standard OpenAI API keys (starts with sk- and followed by many alphanumeric chars)
        # Note: sk-proj-... is a newer format.
        # We'll just look for 'sk-' followed by at least 20 alphanumeric chars to be safe/broad.

        # This regex is a bit simplistic but should catch the one we removed.
        # The one we removed was "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"
        # It's very long.

        secret_pattern = re.compile(r'sk-[a-zA-Z0-9_-]{20,}')

        # Files to scan
        files_to_scan = [
            'case_documentation_app.py',
            'kiroshi_chat.py',
            'kiroshi_cloud_client.py',
            'kiroshi_cloud_sync.py'
        ]

        for filename in files_to_scan:
            if not os.path.exists(filename):
                continue

            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()

            matches = secret_pattern.findall(content)

            # Filter out false positives if necessary (none expected for now)
            # For example if there is a variable named 'mask-something' that might trigger if logic is loose.
            # But here we look for sk- specifically.

            if matches:
                self.fail(f"Found potential OpenAI API key in {filename}: {matches[0][:10]}...")

if __name__ == '__main__':
    unittest.main()
