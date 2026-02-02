
import unittest
from collections import defaultdict
import sys
from unittest.mock import MagicMock

# Mock dependencies
st_mock = MagicMock()
st_mock.session_state = MagicMock()
sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

import json
import dataclasses

# Patch json.dump
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

# Patch dataclasses.asdict
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

import case_documentation_app

class TestClustering(unittest.TestCase):
    def test_clustering_grouping(self):
        titles = [
            "Scanner issue",
            "Scanner connection failed",
            "Login problem",
            "Login problem 2",
            "Random string",
            "Another random string",
            "Scanner issue 2"
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # Scanner related should ideally be clustered
        # "Scanner issue" (0) and "Scanner issue 2" (6) should definitely be together.
        # "Scanner connection failed" (1) shares "scanner" token.

        print(f"Assignments: {assignments}")
        print(f"Labels: {label_map}")

        # Basic check: assignments must have same length as titles
        self.assertEqual(len(assignments), len(titles))

        # Check that 0 and 6 are in same cluster (Scanner issue)
        self.assertEqual(assignments[0], assignments[6])

        # Check that "Login problem" (2) and "Login problem 2" (3) share cluster
        self.assertEqual(assignments[2], assignments[3])

        # Check that "Scanner issue" (0) and "Login problem" (2) are DIFFERENT
        self.assertNotEqual(assignments[0], assignments[2])

    def test_clustering_no_tokens(self):
        # Titles that might result in empty tokens but are similar
        # E.g. extremely short or only stopwords (if stopwords are stripped)
        # Note: _tokenize_issue_description strips stopwords.

        titles = [
            "The issue",
            "The problem",
            "Issue 1",
            "Issue 2"
        ]
        # "issue", "problem" are in TITLE_SIMILARITY_STOPWORDS?
        # TITLE_SIMILARITY_STOPWORDS includes "issue", "problem".
        # So these might have NO tokens.

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        print(f"No tokens assignments: {assignments}")

        # They should form clusters based on normalized string similarity
        # "the issue" vs "the problem" -> base similarity

        self.assertEqual(len(assignments), len(titles))

if __name__ == "__main__":
    unittest.main()
