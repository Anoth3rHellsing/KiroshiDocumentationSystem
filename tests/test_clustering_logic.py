
import sys
import unittest
from unittest.mock import MagicMock
import time
import random
import string
import os
import json

# Mock dependencies
st_mock = MagicMock()
sys.modules["streamlit"] = st_mock
sys.modules["streamlit.errors"] = MagicMock()
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()

sys.modules["altair"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["reportlab"] = MagicMock()
sys.modules["reportlab.lib"] = MagicMock()
sys.modules["reportlab.lib.pagesizes"] = MagicMock()
sys.modules["reportlab.lib.styles"] = MagicMock()
sys.modules["reportlab.platypus"] = MagicMock()
sys.modules["reportlab.graphics.shapes"] = MagicMock()
sys.modules["reportlab.graphics"] = MagicMock()
sys.modules["reportlab.graphics.charts"] = MagicMock()
sys.modules["reportlab.graphics.charts.barcharts"] = MagicMock()
sys.modules["reportlab.graphics.charts.lineplots"] = MagicMock()
sys.modules["reportlab.graphics.widgets"] = MagicMock()
sys.modules["reportlab.graphics.widgets.markers"] = MagicMock()
sys.modules["reportlab.pdfbase"] = MagicMock()

sys.modules["requests"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["urllib3.exceptions"] = MagicMock()

sys.modules["kiroshi_chat"] = MagicMock()
sys.modules["kiroshi_local_ai"] = MagicMock()
sys.modules["kiroshi_cloud_sync"] = MagicMock()
sys.modules["kiroshi_video"] = MagicMock()
sys.modules["kiroshi_hotkeys"] = MagicMock()

# Determine the path to the app
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "case_documentation_app.py")

class TestClusteringLogic(unittest.TestCase):
    _cluster_case_titles = None
    _title_similarity_score = None

    @classmethod
    def setUpClass(cls):
        # Read the file content
        with open(APP_PATH, "r", encoding="utf-8") as f:
            source = f.read()

        # Create a globals dictionary
        cls.app_globals = {
            "__file__": APP_PATH,
            "__name__": "__main__",
            "st": st_mock,
            "json": MagicMock(), # Mock json to prevent serialization errors
        }

        # Configure json.load/loads to return simple data
        cls.app_globals["json"].loads.return_value = {}
        cls.app_globals["json"].load.return_value = {}

        # We need built-in json for non-problematic calls if any?
        # The app uses json.loads/dump.
        # If we mock json module entirely, we might break things if the app relies on real json parsing of strings it creates.
        # But for now, returning empty dicts might be enough to bypass settings loading.

        # Execute the script in the globals dict
        try:
            exec(source, cls.app_globals)
        except Exception as e:
            # print(f"Exec failed: {e}")
            pass

        # Inject _summarize_text if missing (due to early exit)
        if "_summarize_text" not in cls.app_globals:
            cls.app_globals["_summarize_text"] = lambda text, width=80: text[:width] if text else ""

        if "_cluster_case_titles" in cls.app_globals:
            cls._cluster_case_titles = staticmethod(cls.app_globals["_cluster_case_titles"])
            cls._title_similarity_score = staticmethod(cls.app_globals["_title_similarity_score"])
        else:
            raise RuntimeError("Could not load _cluster_case_titles. Check exec failure.")

    def test_clustering_basic(self):
        titles = [
            "Login issue",
            "Login error",
            "Scanner disconnected",
            "Scanner connection failed",
            "Totally unrelated thing",
        ]

        assignments, label_map = self._cluster_case_titles(titles)

        print(f"\nAssignments: {assignments}")
        print(f"Labels: {label_map}")

        self.assertEqual(len(assignments), 5)
        for a in assignments:
            self.assertIn(a, label_map)

    def test_performance(self):
        # Generate synthetic data
        titles = []
        base_titles = [
            "Login failure on Unite",
            "Scanner not connecting",
            "TRIOS 5 calibration error",
            "Dental System crash on startup",
            "Dongle not recognized",
            "Slow performance in design",
            "Order send failed",
            "License expired warning",
        ]

        random.seed(42)
        for _ in range(1000):
            base = random.choice(base_titles)
            suffix = "".join(random.choices(string.ascii_letters, k=5))
            titles.append(f"{base} - {suffix}")

        start_time = time.time()
        self._cluster_case_titles(titles)
        duration = time.time() - start_time

        print(f"\nPerformance test (1000 items): {duration:.4f} seconds")

if __name__ == "__main__":
    unittest.main()
