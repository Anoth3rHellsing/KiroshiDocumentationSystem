
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import types
import dataclasses
import copy
import hashlib

# Mock dependencies
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)

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

def cache_data_mock(*args, **kwargs):
    if args and callable(args[0]):
        return args[0]
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Patches for side effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    if isinstance(obj, MagicMock): return
    try: original_json_dump(obj, fp, **kwargs)
    except TypeError: pass
json.dump = safe_json_dump

original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock): return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Fix RecursionError in deepcopy of MagicMock
MagicMock.__deepcopy__ = lambda self, memo: self

import case_documentation_app

class TestLoadTrackedCasesLogic(unittest.TestCase):

    @patch("case_documentation_app._load_tracked_cases_worker")
    def test_signature_changes(self, mock_worker):
        # Setup mocks for paths
        with patch("case_documentation_app.TRACKED_CASES_DIR") as mock_dir, \
             patch("case_documentation_app.RECENT_CASES_PATH") as mock_recent:

            mock_dir.exists.return_value = True
            mock_recent.exists.return_value = True

            # Scenario 1: Initial state
            mock_dir.stat.return_value.st_mtime = 1000.123456
            mock_recent.stat.return_value.st_mtime = 2000.654321
            st_mock.session_state.get.return_value = None # No last_save_time

            case_documentation_app.load_tracked_cases()

            # Calculate expected signature
            # f"{mtime:.6f}" formatting
            part1 = f"{1000.123456:.6f}"
            part2 = f"{2000.654321:.6f}"
            sig1 = hashlib.md5((part1 + part2).encode("utf-8")).hexdigest()
            mock_worker.assert_called_with(sig1)

            # Scenario 2: Directory mtime changes
            mock_dir.stat.return_value.st_mtime = 1001.000000
            case_documentation_app.load_tracked_cases()
            part1_new = f"{1001.000000:.6f}"
            sig2 = hashlib.md5((part1_new + part2).encode("utf-8")).hexdigest()
            mock_worker.assert_called_with(sig2)
            self.assertNotEqual(sig1, sig2)

            # Scenario 3: Recent cases mtime changes
            mock_recent.stat.return_value.st_mtime = 2001.999999
            case_documentation_app.load_tracked_cases()
            part2_new = f"{2001.999999:.6f}"
            sig3 = hashlib.md5((part1_new + part2_new).encode("utf-8")).hexdigest()
            mock_worker.assert_called_with(sig3)
            self.assertNotEqual(sig2, sig3)

            # Scenario 4: Session state last_save_time changes
            st_mock.session_state.get.return_value = "3000.0"

            case_documentation_app.load_tracked_cases()
            sig4 = hashlib.md5((part1_new + part2_new + "3000.0").encode("utf-8")).hexdigest()
            mock_worker.assert_called_with(sig4)
            self.assertNotEqual(sig3, sig4)

if __name__ == "__main__":
    unittest.main()
