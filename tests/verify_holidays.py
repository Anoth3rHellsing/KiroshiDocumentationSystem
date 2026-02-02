
import sys
import unittest
import json
import dataclasses
from unittest.mock import MagicMock
from datetime import date

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch json.dump to avoid writing mocks to disk during import side-effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        # Check if obj contains mocks (simple check)
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

# Mock dependencies
st_mock = MagicMock()
st_mock.session_state = MagicMock()
# Mock cache_data to verify it's used
def cache_data_mock(*args, **kwargs):
    # Handle @st.cache_data (no parens) case
    if len(args) == 1 and callable(args[0]) and not kwargs:
        func = args[0]
        func._is_cached = True
        return func
    # Handle @st.cache_data(...) case
    def decorator(func):
        func._is_cached = True
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

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

# Add root directory to sys.path
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Import the app
import case_documentation_app

class TestComputeUsHolidays(unittest.TestCase):
    def test_compute_us_holidays_structure(self):
        year = 2025
        holidays = case_documentation_app.compute_us_holidays(year)

        # Check return type
        self.assertIsInstance(holidays, tuple, "compute_us_holidays should return a tuple")

        # Check content
        self.assertTrue(len(holidays) > 0, "Should return holidays")
        self.assertIsInstance(holidays[0], tuple, "Elements should be tuples")
        self.assertIsInstance(holidays[0][0], date, "First element of holiday should be date")
        self.assertIsInstance(holidays[0][1], str, "Second element of holiday should be string")

        # Verify specific holiday (New Year)
        self.assertEqual(holidays[0][0], date(year, 1, 1))
        self.assertEqual(holidays[0][1], "New Year's Day")

        # Verify caching decoration
        # Since we mocked cache_data to set _is_cached, we can check that.
        # But wait, case_documentation_app.py imports streamlit as st.
        # compute_us_holidays is decorated with @st.cache_data.
        # So it should have _is_cached = True if our mock worked.
        self.assertTrue(getattr(case_documentation_app.compute_us_holidays, "_is_cached", False),
                        "compute_us_holidays should be decorated with st.cache_data")

    def test_immutability(self):
        year = 2025
        holidays = case_documentation_app.compute_us_holidays(year)
        try:
            holidays[0] = "mutation attempt"
        except TypeError:
            pass # Expected
        else:
            self.fail("Returned collection should be immutable (tuple)")

if __name__ == "__main__":
    unittest.main()
