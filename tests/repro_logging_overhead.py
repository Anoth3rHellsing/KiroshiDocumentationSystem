
import sys
import unittest.mock
from unittest.mock import MagicMock
import os
import builtins

# Mock streamlit and other dependencies
mock_st = MagicMock()

# Simple cache implementation
_resource_cache = {}
def mock_cache_resource(func=None, **kwargs):
    if func is None:
        return lambda f: mock_cache_resource(f, **kwargs)

    def wrapper(*args, **kwargs):
        key = (func.__name__, args, tuple(sorted(kwargs.items())))
        if key not in _resource_cache:
            _resource_cache[key] = func(*args, **kwargs)
        return _resource_cache[key]
    return wrapper

mock_st.cache_resource = mock_cache_resource
mock_st.cache_data = lambda func=None, **kwargs: (lambda f: f) if func is None else func
sys.modules["streamlit"] = mock_st
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()

# Mock reportlab to avoid import errors
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()

# Mock pywin32 / pythoncom which might be used by imports
sys.modules["pythoncom"] = MagicMock()
sys.modules["win32api"] = MagicMock()
sys.modules["win32con"] = MagicMock()
sys.modules["win32gui"] = MagicMock()
sys.modules["win32ui"] = MagicMock()

# Mock other display/system dependencies
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()

# Mock local modules
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Determine the path to the app
APP_PATH = "case_documentation_app.py"

def run_app_simulation():
    # Read the file content
    with open(APP_PATH, "r", encoding="utf-8") as f:
        code = f.read()

    # Create a globals dictionary to simulate module scope
    # We need to preserve __file__ so the app can resolve paths
    global_vars = {
        "__file__": os.path.abspath(APP_PATH),
        "__name__": "__main__",
    }

    # Execute the code
    exec(code, global_vars)

def measure_overhead():
    print(f"Measuring logging overhead in {APP_PATH}...")

    # Spy on RotatingFileHandler
    with unittest.mock.patch("logging.handlers.RotatingFileHandler") as mock_rfh:
        # Run 1
        print("--- Run 1 ---")
        try:
            run_app_simulation()
        except SystemExit:
            pass # App might call sys.exit
        except Exception as e:
            # We expect some errors because we haven't mocked everything perfectly,
            # but we hope logging setup runs before that.
            print(f"Run 1 stopped with: {e}")

        count_1 = mock_rfh.call_count
        print(f"RotatingFileHandler called {count_1} times")

        # Run 2
        print("--- Run 2 ---")
        try:
            run_app_simulation()
        except SystemExit:
            pass
        except Exception as e:
            print(f"Run 2 stopped with: {e}")

        count_2 = mock_rfh.call_count
        print(f"RotatingFileHandler called {count_2} times (total)")

        new_calls = count_2 - count_1
        print(f"Run 2 triggered {new_calls} new handler instantiations.")

        if new_calls > 0:
            print("❌ Performance Issue Detected: Logging handler re-instantiated on rerun.")
        else:
            print("✅ Optimization Verified: No new handler instantiations on rerun.")

if __name__ == "__main__":
    measure_overhead()
