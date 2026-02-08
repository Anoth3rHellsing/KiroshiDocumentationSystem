
import sys
import unittest
from unittest.mock import MagicMock, patch
import dataclasses

# Patch asdict to handle potential issues with mocks or D initialization
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    try:
        return original_asdict(obj, dict_factory=dict_factory)
    except TypeError:
        return {}
dataclasses.asdict = safe_asdict

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
# Configure get to return default value
def get_mock(key, default=None):
    return default
st_mock.session_state.get = MagicMock(side_effect=get_mock)
# Also support __getitem__
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
# Support __setitem__
st_mock.session_state.__setitem__ = MagicMock()
# Support __contains__
st_mock.session_state.__contains__ = MagicMock(return_value=False)


# Implementing a simple cache to verify behavior
def cache_data_mock(*args, **kwargs):
    def decorator(func):
        cache = {}
        def wrapper(*f_args, **f_kwargs):
            # Create a simple key from arguments
            # Note: str(f_args) works for simple types.
            key = str(f_args) + str(f_kwargs)
            if key not in cache:
                cache[key] = func(*f_args, **f_kwargs)
            return cache[key]
        return wrapper
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Import the app after mocking
import case_documentation_app

class TestCachingPerformance(unittest.TestCase):
    def setUp(self):
        # Reset any state if necessary
        pass

    @patch("case_documentation_app._refresh_and_get_cases")
    @patch("case_documentation_app._calculate_directory_signature")
    def test_load_all_cases_caches_result(self, mock_calc_sig, mock_refresh):
        # Setup mocks
        mock_refresh.return_value = [{"case_id": "1"}]

        # First call: signature "A"
        mock_calc_sig.return_value = "A"
        result1 = case_documentation_app.load_all_cases()
        self.assertEqual(result1, [{"case_id": "1"}])
        self.assertEqual(mock_refresh.call_count, 1)

        # Second call: signature "A" (should be cached)
        result2 = case_documentation_app.load_all_cases()
        self.assertEqual(result2, [{"case_id": "1"}])
        self.assertEqual(mock_refresh.call_count, 1) # Still 1

        # Third call: signature "B" (should refresh)
        mock_calc_sig.return_value = "B"
        mock_refresh.return_value = [{"case_id": "2"}]
        result3 = case_documentation_app.load_all_cases()
        self.assertEqual(result3, [{"case_id": "2"}])
        self.assertEqual(mock_refresh.call_count, 2) # Incremented

    @patch("case_documentation_app._refresh_and_get_cases")
    @patch("case_documentation_app._calculate_directory_signature")
    def test_load_tracked_cases_caches_result(self, mock_calc_sig, mock_refresh):
        # Setup mocks
        # _refresh_and_get_cases returns all cases
        # _filter_tracked_cases filters them. We need to mock _refresh_and_get_cases return value appropriately.
        # But _load_tracked_cases_worker calls _refresh_and_get_cases AND _filter_tracked_cases.
        # We are testing that _load_tracked_cases_worker is cached.

        mock_refresh.return_value = [
            {"case_id": "1", "tracking": {"active": True}},
            {"case_id": "2", "tracking": {"active": False}}
        ]

        # First call: signature "X"
        mock_calc_sig.return_value = "X"
        result1 = case_documentation_app.load_tracked_cases()
        self.assertEqual(len(result1), 1)
        self.assertEqual(result1[0]["case_id"], "1")
        self.assertEqual(mock_refresh.call_count, 1)

        # Second call: signature "X" (cached)
        result2 = case_documentation_app.load_tracked_cases()
        self.assertEqual(len(result2), 1)
        self.assertEqual(mock_refresh.call_count, 1)

        # Third call: signature "Y" (refresh)
        mock_calc_sig.return_value = "Y"
        result3 = case_documentation_app.load_tracked_cases()
        self.assertEqual(len(result3), 1)
        self.assertEqual(mock_refresh.call_count, 2)

if __name__ == "__main__":
    unittest.main()
