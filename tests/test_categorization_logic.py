
import sys
import unittest
from unittest.mock import MagicMock, patch

# Mocking modules before import
class SessionStateMock(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        return MagicMock()

    def __setattr__(self, key, value):
        self[key] = value

mock_st = MagicMock()
mock_st.cache_resource = lambda *args, **kwargs: lambda f: f
mock_st.cache_data = lambda *args, **kwargs: lambda f: f
mock_st.error = MagicMock()
mock_st.warning = MagicMock()
mock_st.info = MagicMock()
mock_st.success = MagicMock()
mock_st.exception = MagicMock()
mock_st.markdown = MagicMock()
mock_st.sidebar = MagicMock()
# Return enough columns to satisfy any st.columns(N) call
mock_st.columns = MagicMock(return_value=[MagicMock() for _ in range(10)])
mock_st.tabs = MagicMock(return_value=[MagicMock() for _ in range(10)])
mock_st.container = MagicMock()
mock_st.session_state = SessionStateMock()

sys.modules["streamlit"] = mock_st
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()

# Mocking other potentially problematic modules
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()

import os
# Ensure root is in path
sys.path.insert(0, os.getcwd())

# Import the module
import case_documentation_app as app

class TestCategorizationLogic(unittest.TestCase):
    def test_tokenize_issue_description(self):
        """Verify _tokenize_issue_description returns lowercase tokens."""
        text = "Scanner Hardware Issue with TRIOS 5"
        tokens = app._tokenize_issue_description(text)

        # Check that tokens are lowercase
        for token in tokens:
            self.assertTrue(token.islower(), f"Token '{token}' is not lowercase")

        self.assertIn("scanner", tokens)
        self.assertIn("hardware", tokens)
        self.assertIn("trios", tokens)

    def test_infer_report_category_correctness(self):
        """Verify _infer_report_category identifies categories correctly."""
        # 3Shape Unite / Login hints: unite, signin, login...

        # Case 1: Login issue
        row = {"category": "Unite Login"}
        tokens = ["unite", "login", "error"]
        category = app._infer_report_category(row, tokens)
        self.assertEqual(category, "3Shape Unite / Login")

        # Case 2: Hardware Connectivity
        row = {"category": "Hardware"}
        tokens = ["scanner", "usb", "connect", "fail"]
        category = app._infer_report_category(row, tokens)
        self.assertEqual(category, "Hardware / Connectivity")

        # Case 3: No match
        row = {"category": "Other"}
        tokens = ["something", "completely", "different"]
        category = app._infer_report_category(row, tokens)
        self.assertIsNone(category)

    def test_infer_report_category_optimization_check(self):
        """
        Verify that the function does NOT re-lowercase tokens (optimization check).
        If we pass uppercase tokens, it should fail to match, proving we removed the redundant .lower().
        """
        row = {}
        tokens = ["UNITE", "LOGIN"]
        # Should return None because keys in hints are lowercase and we expect input to be lowercase
        category = app._infer_report_category(row, tokens)
        self.assertIsNone(category, "Function should not match uppercase tokens (it should assume input is already lowercase)")

    def test_infer_structured_category_correctness(self):
        """Verify _infer_structured_category."""
        # Scanner Hardware
        row = {"scanner_model": "TRIOS 5", "root_cause_code": "HW"}
        tokens = ["hardware", "broken"]
        category = app._infer_structured_category(row, tokens)
        self.assertIsNotNone(category)
        self.assertEqual(category[0], "Scanner Hardware")

    def test_infer_structured_category_optimization_check(self):
        """Verify that the function does NOT re-lowercase tokens (optimization check)."""
        # We use a category that relies on tokens to match.
        # "Software / Installation" matches if token starts with "bug" or "defect".
        row = {}
        tokens = ["BUG"]
        # Should return None because "BUG" does not start with "bug" (case sensitive match now)
        category = app._infer_structured_category(row, tokens)
        self.assertIsNone(category, "Function should not match uppercase tokens (it should assume input is already lowercase)")

if __name__ == "__main__":
    unittest.main()
