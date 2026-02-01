
import sys
import time
import random
import string
import unittest
from unittest.mock import MagicMock

# Mock streamlit and other dependencies
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.colors"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["pyautogui"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["mss"] = MagicMock()
sys.modules["pytesseract"] = MagicMock()
sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()
sys.modules["cryptography"] = MagicMock()

class SessionState(dict):
    def __getattr__(self, key):
        return self.get(key, None)
    def __setattr__(self, key, value):
        self[key] = value

mock_st = MagicMock()
mock_st.session_state = SessionState()
mock_st.session_state.tutorial_metadata = {}
mock_st.session_state.autosave_notice = None
mock_st.session_state.debug_mode = False
# Mock query_params to avoid issue in _extract_theme_query_overrides
mock_st.query_params = {}
sys.modules["streamlit"] = mock_st

import case_documentation_app

class TestClusteringPerformance(unittest.TestCase):
    def test_clustering_correctness_and_speed(self):
        print("Generating titles...")
        random.seed(42)
        base_titles = [
            "Scanner connection issue",
            "Trios 3 disconnects",
            "License expired",
            "Unite login failed",
            "Calibration failed",
            "Scanning extremely slow",
            "Blue screen on startup",
            "Cannot send case",
            "Order form missing",
            "Dongle not recognized"
        ]

        titles = []
        for _ in range(1000):
            base = random.choice(base_titles)
            noise = "".join(random.choices(string.ascii_lowercase, k=5))
            titles.append(f"{base} {noise}")

        print(f"Clustering {len(titles)} titles...")
        start_time = time.time()
        assignments, label_map = case_documentation_app._cluster_case_titles(titles)
        duration = time.time() - start_time

        print(f"Time taken: {duration:.4f} seconds")
        print(f"Number of clusters: {len(label_map)}")

        self.assertEqual(len(assignments), len(titles))
        self.assertTrue(len(label_map) > 0)
        self.assertTrue(isinstance(label_map, dict))

        # Performance check
        self.assertLess(duration, 5.0)

if __name__ == "__main__":
    unittest.main()
