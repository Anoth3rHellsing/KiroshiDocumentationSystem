
import sys
import os
import unittest
from collections import Counter

# Add parent directory to path to import the app
sys.path.append(os.getcwd())

# Import the module under test
import case_documentation_app as app

class TestCategoryInference(unittest.TestCase):

    def test_tokenize_issue_description(self):
        # "login" is in stopwords, so it should be removed.
        # "unite" is not. "credentials" is not.
        text = "Case 12345: User cannot login to Unite with credentials"
        tokens = app._tokenize_issue_description(text)

        self.assertIn("unite", tokens)
        self.assertIn("credentials", tokens)

        # "login" is a stopword in the app
        self.assertNotIn("login", tokens)
        self.assertNotIn("case", tokens)
        self.assertNotIn("12345", tokens)

        # Check lowercase contract
        self.assertTrue(all(t.islower() for t in tokens))

    def test_infer_report_category(self):
        # "3Shape Unite / Login" has tokens: unite, signin... (login is stopword but technically in hints)
        row = {"category": "", "classification": "", "topic": ""}
        tokens = ["unite", "credential", "signin"]

        # We need to verify that we can match a category.
        # "unite" and "signin" should match hints.
        category = app._infer_report_category(row, tokens)
        self.assertEqual(category, "3Shape Unite / Login")

        # Test failure
        tokens_fail = ["banana", "apple"]
        category_fail = app._infer_report_category(row, tokens_fail)
        self.assertIsNone(category_fail)

    def test_infer_structured_category(self):
        # "Scanner Hardware" has scanner_models hints.
        row = {"scanner_model": "TRIOS 5"}
        tokens = ["broken", "scanner"]
        # scanner_model "TRIOS 5" matches hint. Score should be high.

        result = app._infer_structured_category(row, tokens)
        self.assertIsNotNone(result)
        label, score = result
        self.assertEqual(label, "Scanner Hardware")
        self.assertGreater(score, 0)

    def test_summarize_text(self):
        long_text = "This   is  a   text   with   spaces."
        summary = app._summarize_text(long_text, width=50)
        self.assertEqual(summary, "This is a text with spaces.")

        truncated = app._summarize_text(long_text, width=10)
        # "This is a..." or similar. textwrap.shorten appends placeholder if truncated.
        self.assertTrue(len(truncated) <= 10 or truncated.endswith("…"))

if __name__ == '__main__':
    unittest.main()
