import time
import sys
import random
import string
from unittest.mock import MagicMock

# Mock modules to allow importing case_documentation_app
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()

# Mock json.dump to avoid serialization errors during import side-effects
import json
json.dump = MagicMock()

# Mock dataclasses.asdict to handle MagicMock objects
import dataclasses
original_asdict = dataclasses.asdict
def mock_asdict(obj, *args, **kwargs):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, *args, **kwargs)
dataclasses.asdict = mock_asdict

# Determine package root to allow import
from pathlib import Path
APP_DIR = Path(".").resolve()
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Import the function to benchmark
try:
    from case_documentation_app import _cluster_case_titles
except ImportError:
    # Fallback if running from a different directory
    sys.path.insert(0, ".")
    from case_documentation_app import _cluster_case_titles

def generate_random_title(i):
    # Generate disjoint titles to test best-case scenario for inverted index
    return f"uniqueToken{i} specificIssue{i}"

def run_benchmark():
    # Use a fixed seed for reproducibility
    random.seed(42)

    # Generate a dataset
    num_titles = 3000
    titles = [generate_random_title(i) for i in range(num_titles)]

    print(f"Benchmarking _cluster_case_titles with {len(titles)} titles (disjoint)...")

    start_time = time.perf_counter()
    assignments, label_map = _cluster_case_titles(titles)
    end_time = time.perf_counter()

    duration = end_time - start_time
    num_clusters = len(label_map)

    print(f"Time taken: {duration:.4f} seconds")
    print(f"Number of clusters found: {num_clusters}")

    return duration

if __name__ == "__main__":
    run_benchmark()
