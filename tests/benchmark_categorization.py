
import re
import time
import random
from collections import Counter
from functools import lru_cache
from typing import Mapping

# --- Dependencies ---

_CASE_REFERENCE_PATTERN = re.compile(
    r"\b(?:case|caso|ticket|inc(?:ident)?|sr|cs|bug|pr|issue)[-_\s]*\d+\b",
    re.IGNORECASE,
)
_SERIAL_PATTERN = re.compile(r"\b[A-Z]{2,}\d{3,}\b")
_URL_PATTERN = re.compile(r"https?://\S+")
_NON_ALPHANUMERIC_PATTERN = re.compile(r"[^0-9A-Za-z]+")
_LOWER_ALPHANUM_PATTERN = re.compile(r"[^0-9a-z]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_GENERIC_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "have", "error", "issue", "case",
    "user", "when", "failed", "failure", "problem", "unable", "cannot", "customer",
    "reported", "report", "see", "observed", "during", "while", "into", "after",
    "before", "still", "does", "doesnt", "cant", "wont", "need", "needs", "should",
    "could", "would", "please", "help", "team", "agent", "support", "customer",
    "client", "system", "service", "application", "apps", "app", "server", "environment",
    "production", "prod", "dev", "test", "staging", "login", "log", "logs", "message",
    "messages", "details", "detail", "null", "none", "na", "unknown", "new", "open", "closed",
}

_REPORT_CATEGORY_HINTS = {
    "3Shape Unite / Login": {
        "tokens": ("unite", "signin", "sign", "login", "credential", "token", "account", "password", "sesion", "cuenta"),
        "category_terms": ("unite / login", "unite login", "login / unite"),
        "min_score": 2,
    },
    "Dental System / Performance": {
        "tokens": ("performance", "freeze", "crash", "lag", "slow", "render", "rendering", "ds"),
        "category_terms": ("dental system", "ds / performance"),
        "min_score": 2,
    },
}

# --- Original Functions ---

@lru_cache(maxsize=1024)
def _tokenize_issue_description_orig(text: str) -> tuple[str, ...]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _NON_ALPHANUMERIC_PATTERN.sub(" ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return tuple(token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit())

def _infer_report_category_orig(
    row: Mapping[str, object], tokens: list[str]
) -> str | None:
    token_counter = Counter(token.lower() for token in tokens if token)
    if not token_counter:
        return None

    category_fields = []
    for key in ("category", "classification", "topic"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            category_fields.append(value.lower())
    category_blob = " ".join(category_fields)

    scores = {}
    for label, hints in _REPORT_CATEGORY_HINTS.items():
        score = 0
        category_terms = hints.get("category_terms")
        if isinstance(category_terms, (list, tuple, set)):
            for term in category_terms:
                if isinstance(term, str) and term and term in category_blob:
                    score += 4
        token_prefixes = hints.get("tokens")
        if isinstance(token_prefixes, (list, tuple, set)):
            for prefix in token_prefixes:
                if not isinstance(prefix, str) or not prefix:
                    continue
                for token, count in token_counter.items():
                    if token == prefix or token.startswith(prefix):
                        score += count
        if score:
            scores[label] = score

    if not scores:
        return None

    best_label, best_score = max(scores.items(), key=lambda item: item[1])
    threshold_raw = _REPORT_CATEGORY_HINTS.get(best_label, {}).get("min_score", 2)
    try:
        threshold = int(threshold_raw)
    except (TypeError, ValueError):
        threshold = 2
    if best_score >= threshold:
        return best_label
    return None

# --- Optimized Functions ---

@lru_cache(maxsize=1024)
def _tokenize_issue_description_opt(text: str) -> tuple[str, ...]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _NON_ALPHANUMERIC_PATTERN.sub(" ", cleaned)
    # Optimization: One pass for tokenization, lowercasing, and filtering
    result = []
    for token in cleaned.split():
        if len(token) < 3:
            continue
        token_lower = token.lower()
        if token_lower not in _GENERIC_STOPWORDS and not token_lower.isdigit():
            result.append(token_lower)
    return tuple(result)

def _infer_report_category_opt(
    row: Mapping[str, object], tokens: list[str]
) -> str | None:
    # Optimization: Remove redundant lower() and boolean check
    token_counter = Counter(tokens)
    if not token_counter:
        return None

    category_fields = []
    for key in ("category", "classification", "topic"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            category_fields.append(value.lower())
    category_blob = " ".join(category_fields)

    scores = {}
    for label, hints in _REPORT_CATEGORY_HINTS.items():
        score = 0
        category_terms = hints.get("category_terms")
        if isinstance(category_terms, (list, tuple, set)):
            for term in category_terms:
                if isinstance(term, str) and term and term in category_blob:
                    score += 4
        token_prefixes = hints.get("tokens")
        if isinstance(token_prefixes, (list, tuple, set)):
            for prefix in token_prefixes:
                if not isinstance(prefix, str) or not prefix:
                    continue
                for token, count in token_counter.items():
                    if token.startswith(prefix):
                        score += count
        if score:
            scores[label] = score

    if not scores:
        return None

    best_label, best_score = max(scores.items(), key=lambda item: item[1])
    threshold_raw = _REPORT_CATEGORY_HINTS.get(best_label, {}).get("min_score", 2)
    try:
        threshold = int(threshold_raw)
    except (TypeError, ValueError):
        threshold = 2
    if best_score >= threshold:
        return best_label
    return None

# --- Benchmark ---

def run_benchmark():
    # Synthetic data
    descriptions = [
        "User unable to login to 3Shape Unite due to credential error case-12345",
        "Dental System freezing and crashing during rendering performance issue",
        "Just a random description with some numbers 12345 and url https://example.com",
        "Another case with TRIOS calibration drift and tip alignment problems",
        "Short desc",
        "Extremely long description " * 50
    ] * 1000

    row = {"category": "Unite / Login", "classification": "", "topic": ""}

    print("Benchmarking _tokenize_issue_description...")
    start_orig = time.perf_counter()
    tokens_list_orig = []
    for d in descriptions:
        tokens_list_orig.append(_tokenize_issue_description_orig(d))
    end_orig = time.perf_counter()

    start_opt = time.perf_counter()
    tokens_list_opt = []
    for d in descriptions:
        tokens_list_opt.append(_tokenize_issue_description_opt(d))
    end_opt = time.perf_counter()

    print(f"Original Tokenize: {end_orig - start_orig:.4f}s")
    print(f"Optimized Tokenize: {end_opt - start_opt:.4f}s")

    # Verify correctness
    assert tokens_list_orig == tokens_list_opt, "Tokenize results mismatch!"
    print("Tokenize correctness verified.")

    print("\nBenchmarking _infer_report_category...")
    # Prepare tokens for inference (flattened somewhat to simulate real usage)

    start_orig = time.perf_counter()
    for tokens in tokens_list_orig:
        _infer_report_category_orig(row, list(tokens))
    end_orig = time.perf_counter()

    start_opt = time.perf_counter()
    for tokens in tokens_list_opt:
        _infer_report_category_opt(row, list(tokens))
    end_opt = time.perf_counter()

    print(f"Original Infer: {end_orig - start_orig:.4f}s")
    print(f"Optimized Infer: {end_opt - start_opt:.4f}s")

    # Verify correctness
    mismatches = 0
    for i, tokens in enumerate(tokens_list_opt):
        orig = _infer_report_category_orig(row, list(tokens))
        opt = _infer_report_category_opt(row, list(tokens))
        if orig != opt:
            mismatches += 1
            if mismatches < 5:
                print(f"Mismatch at {i}: {orig} != {opt}")

    if mismatches == 0:
        print("Infer correctness verified.")
    else:
        print(f"Infer mismatches: {mismatches}")

if __name__ == "__main__":
    run_benchmark()
