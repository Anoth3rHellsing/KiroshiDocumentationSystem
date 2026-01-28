
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import random
import copy
import dataclasses

# Mock dependencies before importing the app
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

sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["cryptography"] = MagicMock()
sys.modules["cryptography.fernet"] = MagicMock()

# Mock local helper modules to avoid their dependencies
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Mock st.cache_data/resource to passthrough
def cache_data_mock(*args, **kwargs):
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

# Patch json.dump/dataclasses/copy as in repro script
original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        if isinstance(obj, MagicMock): return
        original_json_dump(obj, fp, **kwargs)
    except TypeError: pass
json.dump = safe_json_dump

original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock): return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

original_deepcopy = copy.deepcopy
def safe_deepcopy(x, memo=None, _nil=[]):
    if isinstance(x, MagicMock): return x
    return original_deepcopy(x, memo)
copy.deepcopy = safe_deepcopy

import case_documentation_app

def generate_titles(count=2000):
    patterns = [
        "Scanner connection issue",
        "Scanner connection error",
        "Trios scanner disconnected",
        "Unite login failed",
        "Unite sign-in problem",
        "Login error in Unite",
        "Calibration failed",
        "Calibration tip error",
        "Tip not recognized during calibration",
        "Slow performance in Dental System",
        "Dental System lagging",
        "Lag and freeze in DS",
        "Case upload stuck",
        "Upload timeout",
        "Sending case failed",
        "Network error during upload"
    ]

    # Generate more diverse patterns to create more clusters
    diverse_patterns = []
    for i in range(300):
        # Use unique words to avoid accidental merging or massive candidate lists
        diverse_patterns.append(f"UniqueWord{i} system failure")

    titles = []
    rng = random.Random(42) # Fixed seed for reproducibility

    for i in range(count):
        if i < count * 0.4: # 40% common issues
            base = rng.choice(patterns)
            suffix = rng.choice(["", f" {rng.randint(100, 999)}", " - urgent", " (recurring)"])
            titles.append(f"{base}{suffix}")
        else: # 60% diverse issues (creates many clusters)
            base = rng.choice(diverse_patterns)
            titles.append(f"{base} - detail {rng.randint(1, 100)}")

    return titles

def main():
    titles = generate_titles(2000)
    print(f"Generated {len(titles)} titles.")

    start_time = time.perf_counter()
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)
    end_time = time.perf_counter()

    duration = end_time - start_time
    num_clusters = len(label_map)

    print(f"Clustering took {duration:.4f} seconds.")
    print(f"Produced {num_clusters} clusters.")

    # Validation check (optional, but good for regression testing)
    # With seed 42 and 2000 items, we expect a somewhat consistent number of clusters
    # if the algorithm logic doesn't change significantly (other than speed).

if __name__ == "__main__":
    main()
