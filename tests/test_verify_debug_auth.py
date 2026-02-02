
import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import json
import dataclasses
import copy

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
st_mock.session_state.__getitem__ = MagicMock(return_value=None)
st_mock.session_state.get = MagicMock(return_value=None)
st_mock.cache_resource = lambda func=None, **kwargs: (lambda f: f) if func is None else func
st_mock.cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func

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

# Mock extra modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["kiroshi_cloud_client"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()

# Patch json.dump to avoid side effects
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    if isinstance(obj, MagicMock): return
    original_json_dump(obj, fp, **kwargs)
json.dump = safe_json_dump

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

class TestDebugAuth(unittest.TestCase):
    def setUp(self):
        # Unload module to ensure fresh import for each test
        if "case_documentation_app" in sys.modules:
            del sys.modules["case_documentation_app"]

    def test_auth_constants(self):
        test_user = "sentinel_user"
        test_pass = "sentinel_pass"

        with patch.dict(os.environ, {"KIROSHI_DEBUG_USERNAME": test_user, "KIROSHI_DEBUG_PASSWORD": test_pass}):
            import case_documentation_app

            self.assertEqual(case_documentation_app.DEBUG_USERNAME, test_user)
            self.assertEqual(case_documentation_app.DEBUG_PASSWORD, test_pass)

    def test_api_key_removed(self):
        # Ensure OPENAI_API_KEY is not set in env for this test
        with patch.dict(os.environ):
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]

            import case_documentation_app
            key = case_documentation_app.DEFAULT_OPENAI_API_KEY
            # The hardcoded key was sk-proj-...
            self.assertFalse(key.startswith("sk-proj-"), "Hardcoded API key still present!")
            self.assertEqual(key, "")

if __name__ == "__main__":
    unittest.main()
