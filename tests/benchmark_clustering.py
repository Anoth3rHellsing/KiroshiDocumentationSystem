
import sys
import time
import json
import unittest
from unittest.mock import MagicMock, patch
import random
import string

# Mock dependencies before importing the app
st_mock = MagicMock()
st_mock.session_state = MagicMock()
# Custom dictionary-like mock for session_state to support attribute access and dict methods
class SessionStateMock(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

st_mock.session_state = SessionStateMock()

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
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["pyperclip"] = MagicMock()
sys.modules["pynput"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["cryptography"] = MagicMock()

# Mock st.cache_data/resource factories
def cache_mock(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

st_mock.cache_data = cache_mock
st_mock.cache_resource = cache_mock
st_mock.error = MagicMock()

# Patch json.dump and dataclasses.asdict
import dataclasses
import copy

original_json_dump = json.dump
def safe_json_dump(obj, fp, **kwargs):
    try:
        if isinstance(obj, MagicMock):
            return
        original_json_dump(obj, fp, **kwargs)
    except TypeError:
        pass
json.dump = safe_json_dump

original_asdict = dataclasses.asdict
def safe_asdict(obj, *, dict_factory=dict):
    if isinstance(obj, MagicMock):
        return {}
    return original_asdict(obj, dict_factory=dict_factory)
dataclasses.asdict = safe_asdict

import case_documentation_app

def generate_titles(count=1000):
    base_titles = [
        "Scanner connection issue",
        "Trios 3 calibration failed",
        "Unite login error",
        "Send case stuck at 50%",
        "License expired on dongle",
        "PC blue screen during scan",
        "Cannot export to DCM",
        "Lab inbox not refreshing",
        "Firmware update failed",
        "Move+ touchscreen unresponsive"
    ]

    titles = []
    for _ in range(count):
        base = random.choice(base_titles)
        # Add some variation
        if random.random() < 0.3:
            titles.append(base)
        elif random.random() < 0.6:
            suffix = "".join(random.choices(string.ascii_lowercase, k=5))
            titles.append(f"{base} {suffix}")
        else:
            # Completely random noise
            titles.append(" ".join("".join(random.choices(string.ascii_lowercase, k=random.randint(3, 8))) for _ in range(3)))

    return titles

def benchmark():
    titles = generate_titles(5000)
    print(f"Benchmarking clustering with {len(titles)} titles...")

    start_time = time.perf_counter()
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)
    end_time = time.perf_counter()

    duration = end_time - start_time
    print(f"Clustering took {duration:.4f} seconds")
    print(f"Created {len(label_map)} clusters")

if __name__ == "__main__":
    benchmark()
