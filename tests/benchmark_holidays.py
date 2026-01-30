import sys
import os
import timeit
import datetime
from unittest.mock import MagicMock, patch

# Mock dependencies to avoid side effects and missing packages
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock logging to avoid file handler issues
sys.modules["logging"] = MagicMock()
sys.modules["logging.handlers"] = MagicMock()

# Ensure we can import case_documentation_app
sys.path.append(os.getcwd())

# We need to mock Path.mkdir and Path.exists and open to avoid filesystem errors/creations during import
# Also mock st.session_state access in top level code (e.g. determine_active_theme)
mock_session_state = MagicMock()
mock_session_state.get.return_value = None
sys.modules["streamlit"].session_state = mock_session_state

# Mock dataclasses.asdict to handle MagicMock objects
import dataclasses
original_asdict = dataclasses.asdict
def mock_asdict(obj, *args, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, *args, **kwargs)

# We need to patch where it is used. It is imported in case_documentation_app.
# But we haven't imported case_documentation_app yet.
# We can patch dataclasses.asdict globally for the duration of import?
# No, we need to patch it in the module namespace of case_documentation_app, but we can't do that before import.
# However, if we patch dataclasses.asdict BEFORE import, and case_documentation_app does `from dataclasses import asdict`,
# it will import the patched version IF we modify the module `dataclasses`.

sys.modules["dataclasses"] = dataclasses # ensure it is loaded
dataclasses.asdict = mock_asdict

with patch("pathlib.Path.mkdir"), \
     patch("pathlib.Path.exists", return_value=True), \
     patch("builtins.open", MagicMock()):
    from case_documentation_app import compute_us_holidays

def benchmark():
    print(f"Benchmarking compute_us_holidays...")

    # Warmup
    compute_us_holidays(2025)

    start = timeit.default_timer()
    iterations = 50000
    for _ in range(iterations):
        compute_us_holidays(2025)
        compute_us_holidays(2026)
        compute_us_holidays(2027)
    end = timeit.default_timer()

    total_time = end - start
    avg_time = total_time / (iterations * 3)
    print(f"Time taken for {iterations} iterations (3 calls each): {total_time:.6f} seconds")
    print(f"Average time per call: {avg_time:.9f} seconds")

    # verify output
    result = compute_us_holidays(2025)
    print(f"Result type: {type(result)}")
    if isinstance(result, list):
         print("Result is a list")
    elif isinstance(result, tuple):
         print("Result is a tuple")

if __name__ == "__main__":
    benchmark()
