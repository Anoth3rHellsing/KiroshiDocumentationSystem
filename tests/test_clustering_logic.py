
import sys
import unittest
from unittest.mock import MagicMock

# Mock dependencies
sys.modules["pyautogui"] = MagicMock()
sys.modules["tkinter"] = MagicMock()
sys.modules["PIL.ImageGrab"] = MagicMock()
sys.modules["mss"] = MagicMock()

for mod in ["kiroshi_chat", "kiroshi_local_ai", "kiroshi_cloud_sync", "kiroshi_video", "kiroshi_hotkeys"]:
    sys.modules[mod] = MagicMock()

import case_documentation_app

class TestClusteringLogic(unittest.TestCase):

    def test_title_similarity_score_optimization(self):
        tokens_a = {"apple", "banana", "cherry"}
        tokens_b = {"date", "elderberry", "fig"}
        norm_a = "apple banana cherry"
        norm_b = "date elderberry fig"
        score = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.7
        )
        self.assertEqual(score, 0.0)

    def test_title_similarity_score_pass(self):
        tokens_a = {"apple", "banana", "cherry"}
        tokens_b = {"apple", "banana", "date"}
        norm_a = "apple banana cherry"
        norm_b = "apple banana date"
        score_high = case_documentation_app._title_similarity_score(
            tokens_a, tokens_b, norm_a, norm_b, min_score=0.7
        )
        self.assertGreater(score_high, 0.0)

    def test_cluster_consistency(self):
        # Use terms that are definitely not stopwords
        titles = [
            "KiroshiScanner connection failed",      # 0
            "KiroshiScanner connection error",       # 1
            "MysteriousApp issue",                   # 2
            "MysteriousApp problem",                 # 3
            "Completely unrelated title",            # 4
            "KiroshiScanner connection failed again" # 5
        ]

        clusters, label_map = case_documentation_app._cluster_case_titles(titles)

        unique_clusters = set(clusters)

        # Check assignments
        # 0, 1, 5 should be in same cluster
        self.assertEqual(clusters[0], clusters[1], "Title 0 and 1 should be clustered together")
        self.assertEqual(clusters[0], clusters[5], "Title 0 and 5 should be clustered together")

        # 2, 3 should be in same cluster
        self.assertEqual(clusters[2], clusters[3], "Title 2 and 3 should be clustered together")

        # 4 should be different
        self.assertNotEqual(clusters[4], clusters[0], "Title 4 should be distinct from cluster 0")
        self.assertNotEqual(clusters[4], clusters[2], "Title 4 should be distinct from cluster 2")

        # Expect 3 clusters
        self.assertEqual(len(unique_clusters), 3)

if __name__ == "__main__":
    unittest.main()
