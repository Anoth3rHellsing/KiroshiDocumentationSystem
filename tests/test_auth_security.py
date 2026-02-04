
import sys
import os
import json
import dataclasses
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.query_params = {}
st_mock.experimental_get_query_params = MagicMock(return_value={})

# Patch json.dump to ignore MagicMocks
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        # If the object is a mock, just skip or dump empty dict
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        # If deep inside the object there is a mock, it might still fail
        # But for _persist_setting it dumps the cache which might contain mocks
        pass

json.dump = safe_json_dump

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

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
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock local modules to prevent side effects
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock caching
def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator
st_mock.cache_resource = cache_mock
st_mock.cache_data = cache_mock

# Now import the app
import case_documentation_app

class TestAuthSecurity(unittest.TestCase):
    def test_check_debug_auth_defaults(self):
        """Test authentication with default credentials."""
        # Default is admin/admin
        self.assertTrue(case_documentation_app._check_debug_auth("admin", "admin"))
        self.assertFalse(case_documentation_app._check_debug_auth("admin", "wrong"))
        self.assertFalse(case_documentation_app._check_debug_auth("wrong", "admin"))
        self.assertFalse(case_documentation_app._check_debug_auth("", ""))
        self.assertFalse(case_documentation_app._check_debug_auth(None, None))

    def test_check_debug_auth_env_vars(self):
        """Test authentication with mocked environment variable overrides."""
        # We patch the constants because they are read at module import time
        with patch.object(case_documentation_app, "DEBUG_USERNAME", "super"), \
             patch.object(case_documentation_app, "DEBUG_PASSWORD", "secret"):
            self.assertTrue(case_documentation_app._check_debug_auth("super", "secret"))
            self.assertFalse(case_documentation_app._check_debug_auth("admin", "admin"))
            self.assertFalse(case_documentation_app._check_debug_auth("super", "wrong"))

if __name__ == "__main__":
    unittest.main()
