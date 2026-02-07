
import sys
import time
import random
import unittest.mock
import json
import string

# Helper to mock modules
def mock_module(name):
    sys.modules[name] = unittest.mock.MagicMock()

mock_module("streamlit")
mock_module("streamlit.components.v1")
mock_module("streamlit.errors")
mock_module("pandas")
mock_module("altair")
mock_module("reportlab")
mock_module("reportlab.lib.pagesizes")
mock_module("reportlab.lib")
mock_module("reportlab.lib.styles")
mock_module("reportlab.platypus")
mock_module("reportlab.graphics.shapes")
mock_module("reportlab.graphics.charts.barcharts")
mock_module("reportlab.graphics.charts.lineplots")
mock_module("reportlab.graphics.widgets.markers")
mock_module("pyautogui")
mock_module("tkinter")
mock_module("PIL")
mock_module("pytesseract")
mock_module("mss")
mock_module("requests")
mock_module("urllib3")
mock_module("kiroshi_chat")
mock_module("kiroshi_local_ai")
mock_module("kiroshi_cloud_sync")
mock_module("kiroshi_video")
mock_module("kiroshi_hotkeys")

class MockSessionState(dict):
    def __getattr__(self, key):
        return self.get(key)
    def __setattr__(self, key, value):
        self[key] = value

sys.modules["streamlit"].session_state = MockSessionState()

original_json_dump = json.dump
def mock_json_dump(*args, **kwargs):
    try:
        original_json_dump(*args, **kwargs)
    except TypeError:
        pass

json.dump = mock_json_dump

sys.path.insert(0, ".")

try:
    import case_documentation_app
except ImportError:
    pass
except Exception:
    pass

def benchmark():
    titles = []
    # Generate 500 unique base titles
    base_titles = []
    for i in range(500):
        # Generate random words
        words = ["".join(random.choices(string.ascii_lowercase, k=random.randint(4, 10))) for _ in range(4)]
        base_titles.append(" ".join(words))

    # 2000 total titles
    random.seed(42)
    for _ in range(2000):
        base = random.choice(base_titles)
        if random.random() > 0.3:
            # Slight variation
            titles.append(f"{base} issue {random.randint(1, 100)}")
        else:
            titles.append(base)

    print(f"Benchmarking clustering with {len(titles)} titles...")

    start_time = time.time()
    assignments, label_map = case_documentation_app._cluster_case_titles(titles)
    end_time = time.time()

    duration = end_time - start_time
    print(f"Time taken: {duration:.4f} seconds")
    print(f"Number of clusters: {len(label_map)}")

if __name__ == "__main__":
    benchmark()
