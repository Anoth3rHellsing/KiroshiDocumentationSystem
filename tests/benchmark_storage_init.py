
import sys
import os
import time
import shutil
import tempfile
import pathlib
from unittest.mock import MagicMock, patch

# Mock dependencies
class SessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"'SessionState' object has no attribute '{key}'")
    def __setattr__(self, key, value):
        self[key] = value

st_mock = MagicMock()
st_mock.session_state = SessionState()

def cache_resource_mock(*args, **kwargs):
    def decorator(func):
        cache = {}
        def wrapper(*args, **kwargs):
            key = func.__name__
            if key not in cache:
                cache[key] = func(*args, **kwargs)
            return cache[key]
        return wrapper
    return decorator

def cache_data_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_resource = cache_resource_mock
st_mock.cache_data = cache_data_mock
st_mock.error = MagicMock()
st_mock.markdown = MagicMock()
st_mock.button = MagicMock()
st_mock.info = MagicMock()
st_mock.stop = MagicMock()
st_mock.query_params = {} # Mock query_params
st_mock.experimental_get_query_params = MagicMock(return_value={})

sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
# Mock StreamlitAPIException
class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

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
sys.modules["mss"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["cv2"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Import the app
import case_documentation_app

def benchmark():
    # Setup temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = pathlib.Path(tmpdir)

        # Override paths in the module
        case_documentation_app.DATABASE_DIR = tmp_path / "Database"
        case_documentation_app.UTILITIES_DIR = case_documentation_app.DATABASE_DIR / "utilities"
        case_documentation_app.UPDATES_DIR = case_documentation_app.UTILITIES_DIR / "updates"
        case_documentation_app.RECENT_CASES_PATH = case_documentation_app.UTILITIES_DIR / "recent_cases.json"
        case_documentation_app.TRACKED_CASES_DIR = case_documentation_app.DATABASE_DIR / "TrackedCases"
        case_documentation_app.CASE_ATTACHMENTS_ROOT = tmp_path / "Attachments"

        print(f"Benchmarking _initialize_storage_paths with {case_documentation_app.DATABASE_DIR}")

        # Run benchmark
        start_time = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            case_documentation_app._initialize_storage_paths()
        end_time = time.perf_counter()

        duration = (end_time - start_time) * 1000 # ms
        print(f"_initialize_storage_paths took {duration:.2f}ms for {iterations} calls")
        print(f"Average time per call: {duration/iterations:.4f}ms")

if __name__ == "__main__":
    benchmark()
