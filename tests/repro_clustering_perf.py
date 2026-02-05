
import ast
import sys
import time
import random
import string
import re
from difflib import SequenceMatcher
from functools import lru_cache

def extract_code_from_ast(filename):
    with open(filename, "r") as f:
        tree = ast.parse(f.read())

    definitions = {}
    constants = {}

    needed_funcs = {
        "_cluster_case_titles",
        "_title_similarity_score",
        "_title_similarity_tokens",
        "_normalize_title_similarity",
        "_cached_normalize_title",
        "_tokenize_issue_description",
        "_summarize_text"
    }

    needed_constants = {
        "_CASE_REFERENCE_PATTERN",
        "_SERIAL_PATTERN",
        "_URL_PATTERN",
        "_NON_ALPHANUMERIC_PATTERN",
        "_GENERIC_STOPWORDS",
        "_LOWER_ALPHANUM_PATTERN",
        "_WHITESPACE_PATTERN",
        "TITLE_SIMILARITY_STOPWORDS"
    }

    code_lines = []

    # Imports needed
    code_lines.append("import re")
    code_lines.append("from difflib import SequenceMatcher")
    code_lines.append("from functools import lru_cache")
    code_lines.append("from typing import Sequence, List, Dict, Set, Tuple")

    # We walk the tree and extract top-level assignments and functions
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in needed_constants:
                    code_lines.append(ast.unparse(node))
        elif isinstance(node, ast.FunctionDef):
            if node.name in needed_funcs:
                # Remove decorators if they are not lru_cache, or keep them if they are lru_cache
                # We need to handle decorators carefully.
                # st.cache_data is not available, so we should remove it.
                # lru_cache is available.
                new_decorator_list = []
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "lru_cache":
                        new_decorator_list.append(dec)
                    elif isinstance(dec, ast.Name) and dec.id == "lru_cache":
                        new_decorator_list.append(dec)

                node.decorator_list = new_decorator_list
                code_lines.append(ast.unparse(node))

    return "\n".join(code_lines)

WORDS = ["printer", "scanner", "error", "failed", "connection", "network", "wifi", "timeout", "driver", "install", "update", "windows", "dell", "server", "login", "password", "reset", "urgent", "slow", "crash", "blue", "screen", "power", "cable", "usb", "port", "missing", "corrupt", "data", "file", "system", "boot", "reboot", "disk", "drive", "monitor", "mouse", "keyboard", "click", "sound", "audio", "video", "display", "frozen", "lag", "latency", "ping", "dns", "dhcp", "ip", "address", "subnet", "gateway", "firewall", "proxy", "vpn", "access", "denied", "permission", "admin", "user", "account", "locked", "unlock", "domain", "active", "directory", "policy", "group", "license", "key", "activation", "office", "word", "excel", "outlook", "teams", "sharepoint", "onedrive", "sync", "cloud", "azure", "aws", "google", "chrome", "firefox", "edge", "browser", "cache", "cookie", "history"]

def generate_random_title():
    k = random.randint(3, 8)
    return " ".join(random.choices(WORDS, k=k))

def generate_similar_titles(base, count):
    titles = []
    base_words = base.split()
    for _ in range(count):
        # Mutate base slightly: swap a word, remove a word, add a word
        words = list(base_words)
        op = random.choice(["swap", "remove", "add", "keep"])
        if op == "swap" and words:
            idx = random.randint(0, len(words)-1)
            words[idx] = random.choice(WORDS)
        elif op == "remove" and len(words) > 1:
            idx = random.randint(0, len(words)-1)
            words.pop(idx)
        elif op == "add":
            words.insert(random.randint(0, len(words)), random.choice(WORDS))
        titles.append(" ".join(words))
    return titles

def run_benchmark():
    code = extract_code_from_ast("case_documentation_app.py")

    # Verify optimization is present
    if "min_score" not in code:
        print("WARNING: min_score optimization NOT detected in extracted code!")
    else:
        print("Optimization detected in extracted code.")

    # Execute the extracted code in a local namespace
    namespace = {}
    exec(code, namespace)

    _cluster_case_titles = namespace["_cluster_case_titles"]

    random.seed(42)
    print("Generating data...")
    titles = []
    # Generate some clusters
    for _ in range(200):
        base = generate_random_title()
        titles.append(base)
        titles.extend(generate_similar_titles(base, 10))

    # Add random noise
    for _ in range(1000):
        titles.append(generate_random_title())

    random.shuffle(titles)
    print(f"Benchmarking with {len(titles)} titles...")

    start_time = time.perf_counter()
    assignments, label_map = _cluster_case_titles(titles)
    end_time = time.perf_counter()

    print(f"Time taken: {end_time - start_time:.4f} seconds")
    print(f"Clusters found: {len(label_map)}")

if __name__ == "__main__":
    run_benchmark()
