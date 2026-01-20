
import sys
import time
import random
import string
import json
import dataclasses
from unittest.mock import MagicMock

# Mock dependencies to avoid import errors and side effects
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock specific streamlit attributes used at top level
st_mock = sys.modules["streamlit"]
st_mock.cache_resource = lambda *args, **kwargs: lambda func: func
st_mock.cache_data = lambda *args, **kwargs: lambda func: func
st_mock.query_params = {}
st_mock.experimental_get_query_params.return_value = {}
st_mock.secrets = {}

# Mock StreamlitAPIException
class StreamlitAPIException(Exception): pass
sys.modules["streamlit.errors"].StreamlitAPIException = StreamlitAPIException

# Mock json.dump to avoid serialization errors with MagicMocks
def mock_json_dump(obj, fp, **kwargs):
    pass

original_json_dump = json.dump
json.dump = mock_json_dump

# Mock dataclasses.asdict to handle MagicMock objects
original_asdict = dataclasses.asdict
def mock_asdict(obj):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj)
dataclasses.asdict = mock_asdict

# Now import the module
import case_documentation_app

def generate_titles(count=2000):
    """Generate a mix of repeating and unique titles."""
    base_issues = [
        "Scanner connection failed",
        "Trios 3 calibration error",
        "Unite login timeout",
        "License expired",
        "Slow performance in Dental System",
        "Dongle not recognized",
        "Order creation failed",
        "Cannot send case",
        "Blue screen of death",
        "Installation stuck"
    ]

    titles = []
    # Add some base issues repeatedly
    for _ in range(count // 2):
        titles.append(random.choice(base_issues))

    # Add some unique/varied issues
    for _ in range(count // 2):
        base = random.choice(base_issues)
        suffix = ''.join(random.choices(string.ascii_letters, k=5))
        titles.append(f"{base} {suffix}")

    random.shuffle(titles)
    return titles

def run_benchmark():
    print("Generating titles...")
    titles = generate_titles(5000)
    print(f"Generated {len(titles)} titles.")

    print("Running _cluster_case_titles...")
    start_time = time.time()
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)
    end_time = time.time()

    duration = end_time - start_time
    print(f"Clustering took {duration:.4f} seconds")
    print(f"Created {len(label_map)} clusters")

    # Validation check (basic)
    assert len(assignments) == len(titles)

    return duration, len(label_map)

if __name__ == "__main__":
    run_benchmark()
