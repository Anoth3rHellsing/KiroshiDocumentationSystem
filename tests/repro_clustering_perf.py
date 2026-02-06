
import ast
import time
import random
import sys
from difflib import SequenceMatcher
from functools import lru_cache
import re
import textwrap

def load_code_from_app():
    with open("case_documentation_app.py", "r") as f:
        tree = ast.parse(f.read())

    # We need to extract constants and specific functions
    names_to_extract = {
        "_cluster_case_titles",
        "_title_similarity_score",
        "_title_similarity_tokens",
        "_normalize_title_similarity",
        "_tokenize_issue_description",
        "_cached_normalize_title",
        "_summarize_text",
        "_CASE_REFERENCE_PATTERN",
        "_SERIAL_PATTERN",
        "_URL_PATTERN",
        "_NON_ALPHANUMERIC_PATTERN",
        "_LOWER_ALPHANUM_PATTERN",
        "_WHITESPACE_PATTERN",
        "_GENERIC_STOPWORDS",
        "TITLE_SIMILARITY_STOPWORDS",
    }

    extracted_nodes = []

    # Also need imports
    imports = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
             # We'll just execute imports manually or rely on globals we provide
             pass
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names_to_extract:
                    extracted_nodes.append(node)
        elif isinstance(node, ast.FunctionDef):
            if node.name in names_to_extract:
                extracted_nodes.append(node)

    # Wrap in a module
    module = ast.Module(body=extracted_nodes, type_ignores=[])

    # Execute
    code = compile(module, filename="<ast>", mode="exec")
    namespace = {
        "re": re,
        "SequenceMatcher": SequenceMatcher,
        "lru_cache": lru_cache,
        "textwrap": textwrap,
        "Sequence": list, # close enough
    }
    exec(code, namespace)
    return namespace

def generate_titles(count=1000):
    templates = [
        "Scanner connection issue with {model}",
        "Unite login failed for {user}",
        "TRIOS {model} calibration error",
        "Dental System crashing on startup",
        "Can't send case to lab",
        "Lab inbox empty",
        "Dongle not recognized",
        "License expired for {user}",
        "Update failed error 404",
        "Slow performance in 3Shape Unite",
    ]
    models = ["TRIOS 3", "TRIOS 4", "TRIOS 5", "Move", "Pod"]
    users = ["Dr. Smith", "Clinic A", "User 123", "Admin"]

    titles = []
    for _ in range(count):
        t = random.choice(templates).format(
            model=random.choice(models),
            user=random.choice(users)
        )
        # Add some noise
        if random.random() < 0.3:
            t = f"URGENT: {t}"
        if random.random() < 0.3:
            t = f"{t} - please help"
        titles.append(t)
    return titles

def run_benchmark():
    ns = load_code_from_app()
    _cluster_case_titles = ns["_cluster_case_titles"]

    titles = generate_titles(3000) # Increased to 3000 to see more impact

    start = time.perf_counter()
    _cluster_case_titles(titles)
    end = time.perf_counter()

    print(f"Processed {len(titles)} titles in {end - start:.4f} seconds")

if __name__ == "__main__":
    run_benchmark()
