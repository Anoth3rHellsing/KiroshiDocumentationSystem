import sys
import unittest

from unittest.mock import patch, MagicMock

import streamlit as st

st.cache_data = MagicMock(return_value=lambda f: f)
st.cache_resource = MagicMock(return_value=lambda f: f)

class MockReportlab:
    pass

sys.modules['reportlab'] = MagicMock()
sys.modules['reportlab.lib'] = MagicMock()
sys.modules['reportlab.lib.pagesizes'] = MagicMock()
sys.modules['reportlab.lib.styles'] = MagicMock()
sys.modules['reportlab.lib.validators'] = MagicMock()
sys.modules['reportlab.platypus'] = MagicMock()
sys.modules['reportlab.graphics'] = MagicMock()
sys.modules['reportlab.graphics.shapes'] = MagicMock()
sys.modules['reportlab.graphics.widgets'] = MagicMock()
sys.modules['reportlab.graphics.widgets.markers'] = MagicMock()
sys.modules['kiroshi_chat'] = MagicMock()
sys.modules['kiroshi_local_ai'] = MagicMock()
sys.modules['kiroshi_cloud_sync'] = MagicMock()
sys.modules['kiroshi_video'] = MagicMock()
sys.modules['kiroshi_hotkeys'] = MagicMock()
sys.modules['altair'] = MagicMock()

from case_documentation_app import _cluster_case_titles, _title_similarity_score

class TestClusteringPerf(unittest.TestCase):
    @patch('case_documentation_app.SequenceMatcher')
    def test_matcher_reuse(self, mock_sm):
        # We need mock_sm.ratio() to return something like 0.8
        mock_instance = mock_sm.return_value
        mock_instance.ratio.return_value = 0.8

        titles = ["A", "B"]

        # Call it
        _cluster_case_titles(titles)

        # Check that it only creates the matcher ONCE
        self.assertEqual(mock_sm.call_count, 1)

        # Check that the reused matcher had its seq1 and seq2 changed
        self.assertTrue(mock_instance.set_seq2.called)
        self.assertTrue(mock_instance.set_seq1.called)

if __name__ == '__main__':
    unittest.main()
