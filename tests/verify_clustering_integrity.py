
import sys
import unittest
from unittest.mock import MagicMock
from pathlib import Path

# Mock dependencies before import
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
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
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
sys.modules["cryptography"] = MagicMock()

class SessionState(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)
    def __setattr__(self, key, value):
        self[key] = value

st_mock = sys.modules["streamlit"]
st_mock.session_state = SessionState()
st_mock.cache_resource = lambda *args, **kwargs: lambda func: func
st_mock.cache_data = lambda *args, **kwargs: lambda func: func
st_mock.query_params = {}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import case_documentation_app
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)

class TestClusteringIntegrity(unittest.TestCase):
    def test_clustering_small_dataset(self):
        titles = [
            "Printer error 500",
            "Printer error 501",
            "Network timeout",
            "Network failure",
            "Totally unrelated",
            "Printer error 500",
        ]

        assignments, label_map = case_documentation_app._cluster_case_titles(titles)

        # 0: "Printer error 500" -> Cluster A
        # 1: "Printer error 501" -> Cluster A
        # 2: "Network timeout" -> Cluster B
        # 3: "Network failure" -> Cluster C (Low similarity)
        # 4: "Totally unrelated" -> Cluster D
        # 5: "Printer error 500" -> Cluster A

        self.assertEqual(assignments[0], assignments[5], "Duplicates should cluster together")
        self.assertEqual(assignments[0], assignments[1], "Similar titles should cluster together")

        self.assertNotEqual(assignments[4], assignments[0])

        # Verify network issues are separate or joined based on similarity threshold
        # Based on calc, they are separate.
        self.assertNotEqual(assignments[2], assignments[3], "Low similarity should separate")

    def test_clustering_no_tokens(self):
        titles = ["...", "!!!", "???"]
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        self.assertEqual(len(set(assignments)), 1)
        self.assertEqual(label_map[assignments[0]], "Caso sin título")

if __name__ == "__main__":
    unittest.main()
