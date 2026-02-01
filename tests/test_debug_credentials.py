import unittest
from pathlib import Path

class TestDebugCredentials(unittest.TestCase):
    def test_no_hardcoded_admin_credentials(self):
        """Verify that 'user == "admin" and pw == "admin"' is not present in the codebase."""
        app_path = Path("case_documentation_app.py")
        content = app_path.read_text(encoding="utf-8")

        # This specific pattern was identified as the vulnerability
        vulnerable_pattern = 'if user == "admin" and pw == "admin":'

        self.assertNotIn(vulnerable_pattern, content,
                         "Found hardcoded debug credentials in case_documentation_app.py")

if __name__ == "__main__":
    unittest.main()
