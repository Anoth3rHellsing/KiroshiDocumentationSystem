
import timeit
from collections import Counter
import sys
import os

# Add root to sys.path to import the app
sys.path.append(os.getcwd())

import re
from functools import lru_cache

_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
)
_SERIAL_PATTERN = re.compile(r"\b[A-Z]{2,}\d{3,}\b")
_URL_PATTERN = re.compile(r"https?://\S+")
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^0-9A-Za-z]+")
_GENERIC_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "error", "issue"
}

@lru_cache(maxsize=1024)
def _tokenize_issue_description(text: str) -> tuple[str, ...]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _NON_ALPHANUMERIC_PATTERN.sub(" ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return tuple(token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit())

# Original functions
def _infer_report_category_original(row, tokens) -> str | None:
    token_counter = Counter(token.lower() for token in tokens if token)
    if not token_counter:
        return None
    return "Something"

def _infer_structured_category_original(row, tokens, context=None) -> tuple[str, int] | None:
    token_set = {token.lower() for token in tokens}
    if not token_set:
        return None
    return ("Something", 1)

# Optimized functions
def _infer_report_category_optimized(row, tokens) -> str | None:
    token_counter = Counter(tokens)
    if not token_counter:
        return None
    return "Something"

def _infer_structured_category_optimized(row, tokens, context=None) -> tuple[str, int] | None:
    token_set = set(tokens)
    if not token_set:
        return None
    return ("Something", 1)

# Setup data
description = "This is a test case with some Scanner Hardware issues and connectivity problems resulting in a timeout"
tokens = list(_tokenize_issue_description(description)) * 20 # Make it longer
row = {}

def run_report_original():
    _infer_report_category_original(row, tokens)

def run_report_optimized():
    _infer_report_category_optimized(row, tokens)

def run_structured_original():
    _infer_structured_category_original(row, tokens)

def run_structured_optimized():
    _infer_structured_category_optimized(row, tokens)

iterations = 50000

print("Benchmarking Report Category Inference:")
time_report_orig = timeit.timeit(run_report_original, number=iterations)
time_report_opt = timeit.timeit(run_report_optimized, number=iterations)
print(f"Original: {time_report_orig:.4f}s")
print(f"Optimized: {time_report_opt:.4f}s")
print(f"Speedup: {time_report_orig / time_report_opt:.2f}x")

print("\nBenchmarking Structured Category Inference:")
time_struct_orig = timeit.timeit(run_structured_original, number=iterations)
time_struct_opt = timeit.timeit(run_structured_optimized, number=iterations)
print(f"Original: {time_struct_orig:.4f}s")
print(f"Optimized: {time_struct_opt:.4f}s")
print(f"Speedup: {time_struct_orig / time_struct_opt:.2f}x")
