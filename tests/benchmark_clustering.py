
import time
import random
import string
import re
from functools import lru_cache
from difflib import SequenceMatcher
from typing import Sequence, List, Dict, Set
from collections import defaultdict

# --- Mocked Dependencies from case_documentation_app.py ---

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
    "reported", "report", "see", "observed", "during", "while", "into", "after", "before",
    "still", "does", "doesnt", "cant", "wont", "need", "needs", "should", "could", "would",
    "please", "help", "team", "agent", "support", "customer", "client", "system", "service",
    "application", "apps", "app", "server", "environment", "production", "prod", "dev",
    "test", "staging", "login", "log", "logs", "message", "messages", "details", "detail",
    "null", "none", "na", "unknown", "new", "open", "closed",
}

TITLE_SIMILARITY_STOPWORDS = {
    "issue", "issues", "problem", "problems", "error", "errors", "case", "cases",
    "support", "please", "help", "need",
}

@lru_cache(maxsize=1024)
def _tokenize_issue_description(text: str) -> tuple[str, ...]:
    cleaned = _CASE_REFERENCE_PATTERN.sub(" ", text)
    cleaned = _SERIAL_PATTERN.sub(" ", cleaned)
    cleaned = _URL_PATTERN.sub(" ", cleaned)
    cleaned = _NON_ALPHANUMERIC_PATTERN.sub(" ", cleaned)
    tokens = [token.lower() for token in cleaned.split() if len(token) >= 3]
    return tuple(token for token in tokens if token not in _GENERIC_STOPWORDS and not token.isdigit())

@lru_cache(maxsize=1024)
def _cached_normalize_title(value: str) -> str:
    lowered = value.lower()
    cleaned = _LOWER_ALPHANUM_PATTERN.sub(" ", lowered)
    return _WHITESPACE_PATTERN.sub(" ", cleaned).strip()

def _normalize_title_similarity(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _cached_normalize_title(value)

def _title_similarity_tokens(title: object) -> set[str]:
    if not isinstance(title, str):
        return set()
    return {
        token
        for token in _tokenize_issue_description(title)
        if token not in TITLE_SIMILARITY_STOPWORDS
    }

def _summarize_text(text, width=80):
    return text[:width]

# --- Original Implementation ---

def _title_similarity_score_orig(
    tokens_a: set[str], tokens_b: set[str], norm_a: str, norm_b: str
) -> float:
    if tokens_a and tokens_b and tokens_a.isdisjoint(tokens_b):
        return 0.0

    base = SequenceMatcher(None, norm_a, norm_b).ratio() if (norm_a or norm_b) else 0.0
    if tokens_a and tokens_b:
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = (intersection / union) if union else 0.0
        return 0.6 * base + 0.4 * jaccard
    return base

def _cluster_case_titles_orig(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
    clusters: list[dict[str, object]] = []
    assignments: list[int] = []

    for title in titles:
        normalized = _normalize_title_similarity(title)
        tokens = _title_similarity_tokens(title)

        if not normalized and not tokens:
            blank_index = next(
                (
                    idx
                    for idx, cluster in enumerate(clusters)
                    if not cluster.get("tokens") and not cluster.get("normalized")
                ),
                None,
            )
            if blank_index is None:
                clusters.append(
                    {
                        "normalized": "",
                        "tokens": set(),
                        "label": "Caso sin título",
                    }
                )
                blank_index = len(clusters) - 1
            assignments.append(blank_index)
            continue

        best_index = -1
        best_score = 0.0
        for idx, cluster in enumerate(clusters):
            cluster_tokens = cluster.get("tokens") or set()
            cluster_norm = str(cluster.get("normalized") or "")
            score = _title_similarity_score_orig(tokens, cluster_tokens, normalized, cluster_norm)
            if score > best_score:
                best_score = score
                best_index = idx

        threshold = 0.68 if tokens else 0.8
        if best_index == -1 or best_score < threshold:
            label_source = title if isinstance(title, str) and title.strip() else normalized
            label = (
                _summarize_text(label_source, width=80)
                if label_source
                else "Caso sin título"
            )
            clusters.append(
                {
                    "normalized": normalized,
                    "tokens": set(tokens),
                    "label": label,
                }
            )
            assignments.append(len(clusters) - 1)
        else:
            cluster = clusters[best_index]
            cluster_tokens = cluster.setdefault("tokens", set())
            cluster_tokens.update(tokens)
            cluster["normalized"] = cluster.get("normalized") or normalized
            if isinstance(title, str) and title.strip():
                candidate_label = _summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map

# --- Optimized Implementation (with Pruning) ---

def _title_similarity_score_pruned(
    tokens_a: set[str], tokens_b: set[str], norm_a: str, norm_b: str, threshold: float = 0.0
) -> float:
    if tokens_a and tokens_b:
        if tokens_a.isdisjoint(tokens_b):
            return 0.0

        # Calculate Jaccard contribution
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = (intersection / union) if union else 0.0

        # Max possible score is when SequenceMatcher ratio is 1.0
        # Score = 0.6 * base + 0.4 * jaccard
        max_theoretical_score = 0.6 + 0.4 * jaccard

        # Using a small epsilon for float comparison safety
        if max_theoretical_score <= threshold + 1e-9:
            return 0.0 # Cannot beat best_score

        base = SequenceMatcher(None, norm_a, norm_b).ratio() if (norm_a or norm_b) else 0.0
        return 0.6 * base + 0.4 * jaccard

    base = SequenceMatcher(None, norm_a, norm_b).ratio() if (norm_a or norm_b) else 0.0
    return base

def _cluster_case_titles_pruned(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
    clusters: list[dict[str, object]] = []
    assignments: list[int] = []

    for title in titles:
        normalized = _normalize_title_similarity(title)
        tokens = _title_similarity_tokens(title)

        if not normalized and not tokens:
            blank_index = next(
                (
                    idx
                    for idx, cluster in enumerate(clusters)
                    if not cluster.get("tokens") and not cluster.get("normalized")
                ),
                None,
            )
            if blank_index is None:
                clusters.append(
                    {
                        "normalized": "",
                        "tokens": set(),
                        "label": "Caso sin título",
                    }
                )
                blank_index = len(clusters) - 1
            assignments.append(blank_index)
            continue

        best_index = -1
        best_score = 0.0
        for idx, cluster in enumerate(clusters):
            cluster_tokens = cluster.get("tokens") or set()
            cluster_norm = str(cluster.get("normalized") or "")

            # Pass best_score as threshold
            score = _title_similarity_score_pruned(tokens, cluster_tokens, normalized, cluster_norm, threshold=best_score)

            if score > best_score:
                best_score = score
                best_index = idx

        threshold = 0.68 if tokens else 0.8
        if best_index == -1 or best_score < threshold:
            label_source = title if isinstance(title, str) and title.strip() else normalized
            label = (
                _summarize_text(label_source, width=80)
                if label_source
                else "Caso sin título"
            )
            clusters.append(
                {
                    "normalized": normalized,
                    "tokens": set(tokens),
                    "label": label,
                }
            )
            assignments.append(len(clusters) - 1)
        else:
            cluster = clusters[best_index]
            cluster_tokens = cluster.setdefault("tokens", set())
            cluster_tokens.update(tokens)
            cluster["normalized"] = cluster.get("normalized") or normalized
            if isinstance(title, str) and title.strip():
                candidate_label = _summarize_text(title, width=80)
                if len(candidate_label) > len(str(cluster.get("label") or "")):
                    cluster["label"] = candidate_label
            assignments.append(best_index)

    label_map = {idx: str(cluster.get("label") or "Caso sin título") for idx, cluster in enumerate(clusters)}
    return assignments, label_map

# --- Benchmark Code ---

def generate_titles(n):
    base_titles = [
        "Connection issue with scanner",
        "Scanner not connecting",
        "TRIOS scanner disconnected",
        "Login failed on Unite",
        "Cannot login to 3Shape Account",
        "Password reset not working",
        "Slow performance in Dental System",
        "Dental System freezing",
        "Lag when designing",
        "Calibration failed",
        "Tip not recognized",
        "Hardware error 22",
        "Order creation failed",
        "Cannot send order",
        "Order stuck in outbox",
    ]
    titles = []
    rng = random.Random(42) # Fixed seed for reproducibility
    for _ in range(n):
        base = rng.choice(base_titles)
        suffix = ''.join(rng.choices(string.ascii_uppercase + string.digits, k=5))
        titles.append(f"{base} - {suffix}")
    return titles

def verify_correctness():
    print("Verifying correctness...")
    titles = generate_titles(200) # Small batch for verification
    assign_orig, map_orig = _cluster_case_titles_orig(titles)
    assign_opt, map_opt = _cluster_case_titles_pruned(titles)

    if assign_orig == assign_opt:
        print("✅ Assignments match exactly.")
    else:
        print("❌ Assignments mismatch!")
        mismatches = 0
        for i, (a, b) in enumerate(zip(assign_orig, assign_opt)):
            if a != b:
                mismatches += 1
                if mismatches < 5:
                    print(f"Index {i}: Orig {a} vs Opt {b}")
        print(f"Total mismatches: {mismatches}")

    # We don't check labels strictly as they depend on assignment order/content which should be same
    # but slight float diffs *could* affect winner if scores are identical.
    # But here we used same logic so scores should be identical.

def benchmark():
    sizes = [100, 500, 1000]
    results_orig = {}
    results_opt = {}
    print("\nBenchmarking...")
    for size in sizes:
        titles = generate_titles(size)

        # Original
        start_time = time.perf_counter()
        _cluster_case_titles_orig(titles)
        end_time = time.perf_counter()
        duration_orig = end_time - start_time
        results_orig[size] = duration_orig

        # Optimized (Pruned)
        start_time = time.perf_counter()
        _cluster_case_titles_pruned(titles)
        end_time = time.perf_counter()
        duration_opt = end_time - start_time
        results_opt[size] = duration_opt

        speedup = duration_orig / duration_opt
        print(f"Size: {size}, Orig: {duration_orig:.4f}s, Opt: {duration_opt:.4f}s, Speedup: {speedup:.2f}x")

    # Check scaling
    ratio_1000_500_orig = results_orig[1000] / results_orig[500]
    ratio_1000_500_opt = results_opt[1000] / results_opt[500]
    print(f"\nOrig Scaling 1000/500: {ratio_1000_500_orig:.2f}x")
    print(f"Opt Scaling 1000/500: {ratio_1000_500_opt:.2f}x")

if __name__ == "__main__":
    verify_correctness()
    benchmark()
