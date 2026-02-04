import time
import sys
import os
import random
import string

# Ensure we can import the app
sys.path.append(os.getcwd())

import case_documentation_app
from case_documentation_app import _cluster_case_titles

def generate_titles(count=200):
    base_titles = [
        "Scanner connection issue",
        "Trios 3 calibration failed",
        "Unite login error",
        "License expired",
        "Performance slow",
        "Cannot send case",
        "Dongle not recognized",
        "Blue screen crash",
        "Installation failed",
        "Update stuck"
    ]
    titles = []
    for _ in range(count):
        base = random.choice(base_titles)
        # Add random suffix to make them slightly different but clusterable
        suffix = ''.join(random.choices(string.ascii_lowercase + " ", k=10))
        titles.append(f"{base} {suffix}")
    return titles

def benchmark():
    titles = generate_titles(500)
    print(f"Benchmarking clustering with {len(titles)} titles...")

    start_time = time.time()
    _cluster_case_titles(titles)
    end_time = time.time()

    print(f"Time taken: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark()
