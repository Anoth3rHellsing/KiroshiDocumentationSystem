
import sys
import unittest
import json
import time
from unittest.mock import MagicMock, patch
from pathlib import Path
import copy
import dataclasses

# Mock dependencies before importing the app
st_mock = MagicMock()
# Mock session_state as a MagicMock to allow attribute access
st_mock.session_state = MagicMock()
# Ensure dictionary-like behavior for session_state if needed (though app uses attribute access mostly)
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
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = MagicMock()
sys.modules["cryptography.hazmat"] = MagicMock()
sys.modules["cryptography.hazmat.primitives"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf"] = MagicMock()
sys.modules["cryptography.hazmat.primitives.kdf.pbkdf2"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Mock st.cache_data to do nothing (passthrough)
def cache_data_mock(*args, **kwargs):
    # Check if used as decorator without arguments: @st.cache_data
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]

    # Used as factory: @st.cache_data(ttl=...)
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_data_mock
st_mock.cache_resource = cache_data_mock
st_mock.error = MagicMock()

# Define StreamlitAPIException
class StreamlitAPIException(Exception):
    pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

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

# Patch dataclasses.asdict to handle mocks
original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

# Patch deepcopy to handle mocks
original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock):
        return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

import case_documentation_app

class TestRefreshAndGetCases(unittest.TestCase):
    def setUp(self):
        # Reset cache before each test if possible
        pass

    @patch("os.scandir")
    def test_refresh_sorting_robustness(self, mock_scandir):
        # Mock scandir to return files
        file1 = MagicMock()
        file1.is_file.return_value = True
        file1.name = "case1.json"
        file1.path = "/tmp/case1.json"
        file1.stat.return_value.st_mtime = 1672567200.0 # 2023-01-01

        file2 = MagicMock()
        file2.is_file.return_value = True
        file2.name = "case2.json"
        file2.path = "/tmp/case2.json"
        file2.stat.return_value.st_mtime = 1672653600.0 # 2023-01-02

        mock_scandir.return_value.__enter__.return_value = [file1, file2]

        # Patch Path at the module level where it is used
        with patch("case_documentation_app.Path") as MockPath:
            # Setup MockPath instances
            inst1 = MagicMock()
            inst1.read_text.return_value = json.dumps({
                "case_id": "CASE-1",
                "last_modified": "2023-01-01T10:00:00"
            })
            inst1.stem = "case1"

            inst2 = MagicMock()
            inst2.read_text.return_value = json.dumps({
                "case_id": "CASE-2",
                "last_modified": "2023-01-02T10:00:00"
            })
            inst2.stem = "case2"

            def path_side_effect(path):
                # When Path(path) is called
                if "case1" in str(path):
                    return inst1
                if "case2" in str(path):
                    return inst2

                # For other paths (directories), return a mock that exists
                m = MagicMock()
                m.exists.return_value = True
                m.resolve.return_value = m # For resolve() calls
                return m

            MockPath.side_effect = path_side_effect
            # Also mock home() class method if used
            MockPath.home.return_value = MagicMock()

            # Ensure directories are treated as existing
            # directories in app are global variables initialized at import time
            # But inside _refresh_and_get_cases loop: if not directory.exists()
            # directory is an instance of real Path (from import time)
            # So mocking case_documentation_app.Path doesn't affect existing instances.

            # Use os.path.exists patching? Or patch the global variables?
            # case_documentation_app.DATABASE_DIR is a Path object.
            # We can try to patch os.path.exists?
            # Or assume they exist in the sandbox environment (which they do: DATABASE_DIR created in import?)
            # DATABASE_DIR = Path("C:/ProgramFiles/KiroshiDatabase") on Windows
            # or Path.home() / "KiroshiDatabase" on Linux.

            # Since we are on Linux (presumably), it's in home dir.
            # The app creates them at module level?

            # Let's inspect DATABASE_DIR in app.
            # print(f"DEBUG: {case_documentation_app.DATABASE_DIR}")

            # If they don't exist, _refresh_and_get_cases skips them.
            # We need them to exist.
            # We can patch 'pathlib.Path.exists' globally?

            with patch("pathlib.Path.exists", return_value=True):
                 cases = case_documentation_app._refresh_and_get_cases()

            self.assertEqual(len(cases), 2)

            # Verify order (Reverse chronological)
            # CASE-2 (Jan 2) should be first
            self.assertEqual(cases[0]["case_id"], "CASE-2")
            self.assertEqual(cases[1]["case_id"], "CASE-1")

            # Check if _updated_ts is present
            has_ts = "_updated_ts" in cases[0]
            print(f"Has _updated_ts: {has_ts}")

            self.assertTrue(has_ts, "_updated_ts should be present")

if __name__ == "__main__":
    unittest.main()
