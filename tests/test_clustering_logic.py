
import unittest
import sys
import ast
import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Sequence, Mapping, Dict, List, Any, Iterable, Callable
import math

class TestClusteringLogic(unittest.TestCase):
    def setUp(self):
        # Read the file content
        with open("case_documentation_app.py", "r", encoding="utf-8") as f:
            content = f.read()

        self.context = {
            "re": re,
            "SequenceMatcher": SequenceMatcher,
            "lru_cache": lru_cache,
            "Sequence": Sequence,
            "Mapping": Mapping,
            "Dict": Dict,
            "List": List,
            "Any": Any,
            "Iterable": Iterable,
            "Callable": Callable,
            "math": math,
            # Mock _summarize_text as it is used in _cluster_case_titles
            "_summarize_text": lambda text, width=80: text[:width]
        }

        tree = ast.parse(content)

        # Nodes to execute
        nodes_to_exec = []

        target_names = {
            "_LOWER_ALPHANUM_PATTERN",
            "_WHITESPACE_PATTERN",
            "_CASE_REFERENCE_PATTERN",
            "_SERIAL_PATTERN",
            "_URL_PATTERN",
            "_NON_ALPHANUMERIC_PATTERN",
            "_GENERIC_STOPWORDS",
            "TITLE_SIMILARITY_STOPWORDS",
            "_tokenize_issue_description",
            "_cached_normalize_title",
            "_normalize_title_similarity",
            "_title_similarity_tokens",
            "_title_similarity_score",
            "_cluster_case_titles"
        }

        for node in tree.body:
            if isinstance(node, ast.Assign):
                # Check targets
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in target_names:
                        nodes_to_exec.append(node)
                        break
            elif isinstance(node, ast.FunctionDef):
                if node.name in target_names:
                    nodes_to_exec.append(node)

        # Execute selected nodes
        for node in nodes_to_exec:
            # Wrap in Module to be compilable
            wrapper = ast.Module(body=[node], type_ignores=[])
            # Ensure line numbers are fixed (not strictly necessary but good practice)
            ast.fix_missing_locations(wrapper)
            code = compile(wrapper, filename="<string>", mode="exec")
            exec(code, self.context)

        self.score_func = self.context["_title_similarity_score"]
        self.cluster_func = self.context["_cluster_case_titles"]
        self.normalize_func = self.context["_normalize_title_similarity"]
        self.tokenize_func = self.context["_title_similarity_tokens"]

    def test_similarity_score_identical(self):
        t1 = "System down"
        norm1 = self.normalize_func(t1)
        tok1 = self.tokenize_func(t1)

        score = self.score_func(tok1, tok1, norm1, norm1)
        self.assertAlmostEqual(score, 1.0)

    def test_similarity_score_disjoint(self):
        t1 = "System down"
        t2 = "Coffee break"
        norm1 = self.normalize_func(t1)
        tok1 = self.tokenize_func(t1)
        norm2 = self.normalize_func(t2)
        tok2 = self.tokenize_func(t2)

        score = self.score_func(tok1, tok2, norm1, norm2)
        self.assertEqual(score, 0.0)

    def test_similarity_score_threshold_optimization(self):
        # Construct a case where optimization should kick in
        # We use fruits to avoid stopword filtering
        t1 = "banana apple cherry date"
        t2 = "banana apple fig grape"
        # Shared: banana, apple (2)
        # Unique: cherry, date, fig, grape (4)
        # Union: 6. Jaccard: 2/6 = 0.333...
        # Max score: 0.6 + 0.4 * 0.333 = 0.733

        norm1 = self.normalize_func(t1)
        tok1 = self.tokenize_func(t1)
        norm2 = self.normalize_func(t2)
        tok2 = self.tokenize_func(t2)

        # If threshold is 0.8, it should return 0.0 because max possible (0.733) < 0.8
        score = self.score_func(tok1, tok2, norm1, norm2, threshold=0.8)
        self.assertEqual(score, 0.0)

        # If threshold is 0.5, it should calculate the real score because max possible (0.733) > 0.5
        score_real = self.score_func(tok1, tok2, norm1, norm2, threshold=0.5)
        self.assertGreater(score_real, 0.0)

    def test_clustering(self):
        titles = [
            "Scanner connection issue",
            "Scanner connection failed", # Should cluster with above
            "Unite login problem",
            "Unite login error", # Should cluster with above
            "Completely unrelated thing"
        ]

        assignments, label_map = self.cluster_func(titles)

        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[2], assignments[3])
        self.assertNotEqual(assignments[0], assignments[2])
        self.assertNotEqual(assignments[0], assignments[4])
        self.assertEqual(len(label_map), 3) # Should be 3 clusters

if __name__ == "__main__":
    unittest.main()
