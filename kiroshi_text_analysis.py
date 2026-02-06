# -*- coding: utf-8 -*-
"""
Kiroshi Text Analysis Module
Extracted from case_documentation_app.py for performance optimization.
"""

from __future__ import annotations

import re
import textwrap
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Mapping, Sequence

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
    "the",
    "and",
    "for",
    "with",
    "that",
    "from",
    "this",
    "have",
    "error",
    "issue",
    "case",
    "user",
    "when",
    "failed",
    "failure",
    "problem",
    "unable",
    "cannot",
    "customer",
    "reported",
    "report",
    "see",
    "observed",
    "during",
    "while",
    "into",
    "after",
    "before",
    "still",
    "does",
    "doesnt",
    "cant",
    "wont",
    "need",
    "needs",
    "should",
    "could",
    "would",
    "please",
    "help",
    "team",
    "agent",
    "support",
    "customer",
    "client",
    "system",
    "service",
    "application",
    "apps",
    "app",
    "server",
    "environment",
    "production",
    "prod",
    "dev",
    "test",
    "staging",
    "login",
    "log",
    "logs",
    "message",
    "messages",
    "details",
    "detail",
    "null",
    "none",
    "na",
    "unknown",
    "new",
    "open",
    "closed",
}


TITLE_SIMILARITY_STOPWORDS = {
    "issue",
    "issues",
    "problem",
    "problems",
    "error",
    "errors",
    "case",
    "cases",
    "support",
    "please",
    "help",
    "need",
}


_REPORT_CATEGORY_HINTS: dict[str, dict[str, object]] = {
    "3Shape Unite / Login": {
        "tokens": (
            "unite",
            "signin",
            "sign",
            "login",
            "credential",
            "token",
            "account",
            "password",
            "sesion",
            "cuenta",
        ),
        "category_terms": (
            "unite / login",
            "unite login",
            "login / unite",
        ),
        "min_score": 2,
    },
    "3Shape Unite / Case Submission": {
        "tokens": (
            "proxy",
            "timeout",
            "firewall",
            "submission",
            "submit",
            "upload",
            "envio",
            "enviar",
            "case",
            "inbox",
            "transfer",
        ),
        "category_terms": (
            "unite / case",
            "unite / submission",
            "case submission",
            "send case",
        ),
        "min_score": 2,
    },
    "TRIOS / Calibration": {
        "tokens": (
            "calibr",
            "drift",
            "tip",
            "aline",
            "alignment",
            "dongle",
            "firmware",
            "led",
        ),
        "category_terms": (
            "trios / calibration",
            "calibration",
        ),
        "min_score": 1,
    },
    "TRIOS / Scan Quality": {
        "tokens": (
            "scan",
            "occlusion",
            "margin",
            "artefact",
            "artifact",
            "noise",
            "texture",
            "superpos",
            "detalle",
            "detail",
        ),
        "category_terms": (
            "trios / scan",
            "scan quality",
        ),
        "min_score": 2,
    },
    "Dental System / Performance": {
        "tokens": (
            "performance",
            "freeze",
            "crash",
            "lag",
            "slow",
            "render",
            "rendering",
            "ds",
        ),
        "category_terms": (
            "dental system",
            "ds / performance",
        ),
        "min_score": 2,
    },
    "Hardware / Connectivity": {
        "tokens": (
            "usb",
            "power",
            "cable",
            "battery",
            "connect",
            "conexion",
            "bluetooth",
            "wifi",
            "ethernet",
            "adapter",
        ),
        "category_terms": (
            "hardware",
            "connectivity",
        ),
        "min_score": 2,
    },
    "Software / Installation": {
        "tokens": (
            "install",
            "setup",
            "installer",
            "update",
            "upgrade",
            "patch",
            "deploy",
            "reinstall",
        ),
        "category_terms": (
            "installation",
            "software install",
        ),
        "min_score": 2,
    },
    "Account / Licensing": {
        "tokens": (
            "license",
            "licence",
            "licencia",
            "activation",
            "renew",
            "billing",
            "suscription",
            "subscription",
        ),
        "category_terms": (
            "license",
            "licensing",
            "licencia",
        ),
        "min_score": 1,
    },
    "Data Management": {
        "tokens": (
            "database",
            "backup",
            "restore",
            "export",
            "import",
            "sync",
            "sinc",
            "storage",
        ),
        "category_terms": (
            "data management",
            "database",
        ),
        "min_score": 2,
    },
}


_STRUCTURED_CATEGORY_HINTS: dict[str, dict[str, object]] = {
    "Scanner Hardware": {
        "scanner_models": (
            "trios 3",
            "trios3",
            "trios 4",
            "trios4",
            "trios 5",
            "trios5",
            "trios move",
            "trios move+",
            "move+",
            "move plus",
            "pod",
            "pod 3",
            "pod 4",
            "go",
        ),
        "root_cause_codes": (
            "hw",
            "hardware",
            "scanner",
            "device",
        ),
        "recurrence_threshold": 2,
    },
    "Software / Installation": {
        "root_cause_codes": (
            "bug",
            "sw",
            "software",
            "defect",
        ),
        "tokens": ("bug", "defect"),
        "recurrence_threshold": 1,
    },
    "Hardware / Connectivity": {
        "root_cause_codes": (
            "net",
            "network",
            "connect",
            "vpn",
            "wifi",
        ),
    },
    "Workflow Guidance": {
        "root_cause_codes": (
            "workflow",
            "training",
            "usage",
            "user",
        ),
    },
    "Account / Licensing": {
        "root_cause_codes": (
            "lic",
            "license",
            "licensing",
        ),
    },
    "Data Management": {
        "root_cause_codes": (
            "db",
            "database",
            "backup",
            "restore",
            "sync",
        ),
    },
}


def _summarize_text(text: str, width: int = 200) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    try:
        return textwrap.shorten(cleaned, width=width, placeholder="…")
    except Exception:
        return cleaned[:width]


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


def _title_similarity_score(
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


def _cluster_case_titles(titles: Sequence[str]) -> tuple[list[int], dict[int, str]]:
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
            score = _title_similarity_score(tokens, cluster_tokens, normalized, cluster_norm)
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


@lru_cache(maxsize=1024)
def _cached_normalize_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip().lower()


def _normalize_text_field(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _cached_normalize_text(value)


def _coerce_int(value: object, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _infer_report_category(
    row: Mapping[str, object], tokens: list[str]
) -> str | None:
    token_counter = Counter(token.lower() for token in tokens if token)
    if not token_counter:
        return None

    category_fields: list[str] = []
    for key in ("category", "classification", "topic"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            category_fields.append(value.lower())
    category_blob = " ".join(category_fields)

    scores: dict[str, int] = {}
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


def _infer_structured_category(
    row: Mapping[str, object], tokens: list[str], context: Mapping[str, object] | None = None
) -> tuple[str, int] | None:
    context = context or {}
    scanner_candidates = [
        row.get("scanner_model"),
        row.get("scanner"),
        row.get("scanner_type"),
        row.get("scanner_sn"),
    ]
    scanner_model = ""
    for candidate in scanner_candidates:
        if isinstance(candidate, str) and candidate.strip():
            scanner_model = candidate.strip()
            break

    scanner_norm = _normalize_text_field(scanner_model)
    root_cause_code = row.get("root_cause_code") or row.get("root_cause_id")
    if isinstance(root_cause_code, str):
        root_cause_code_norm = _normalize_text_field(root_cause_code)
    elif isinstance(root_cause_code, (int, float)):
        root_cause_code_norm = str(root_cause_code)
    else:
        root_cause_code_norm = ""

    root_cause_text = _normalize_text_field(row.get("root_cause"))
    recurrence_count = _coerce_int(row.get("recurrence_count"), 0)
    structured_scores: dict[str, int] = {}

    token_set = {token.lower() for token in tokens}

    for label, hints in _STRUCTURED_CATEGORY_HINTS.items():
        score = 0
        codes = hints.get("root_cause_codes")
        if codes:
            for candidate in codes:
                candidate_norm = _normalize_text_field(candidate)
                if not candidate_norm:
                    continue
                if root_cause_code_norm and (
                    root_cause_code_norm == candidate_norm
                    or root_cause_code_norm.startswith(candidate_norm)
                ):
                    score += 8
                if candidate_norm and candidate_norm in root_cause_text:
                    score += 3
        scanner_models = hints.get("scanner_models")
        if scanner_models and scanner_norm:
            for candidate in scanner_models:
                candidate_norm = _normalize_text_field(candidate)
                if not candidate_norm:
                    continue
                if scanner_norm == candidate_norm or scanner_norm.startswith(candidate_norm):
                    score += 6
        token_prefixes = hints.get("tokens")
        if token_prefixes:
            for prefix in token_prefixes:
                prefix_norm = _normalize_text_field(prefix)
                if not prefix_norm:
                    continue
                for token in token_set:
                    if token.startswith(prefix_norm):
                        score += 1
        threshold = _coerce_int(hints.get("recurrence_threshold"), 0)
        if threshold and recurrence_count >= threshold:
            score += 2
        if score:
            structured_scores[label] = score

    if not structured_scores:
        return None

    return max(structured_scores.items(), key=lambda item: item[1])


def _derive_analysis_label(
    row: Mapping[str, object], context: Mapping[str, object] | None = None
) -> str:
    context = context or {}
    recurrence_count = _coerce_int(row.get("recurrence_count"), 0)

    title_cluster_label = row.get("title_cluster_label")
    if isinstance(title_cluster_label, str):
        cluster_label = title_cluster_label.strip()
        if cluster_label:
            if recurrence_count >= 3 and "Recurring" not in cluster_label:
                return f"{cluster_label} (Recurring)"
            return cluster_label

    text_candidates: list[str] = []
    for key in (
        "category",
        "classification",
        "topic",
        "root_cause",
        "title",
        "description_excerpt",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            text_candidates.append(value)

    tokens: list[str] = []
    for text in text_candidates:
        tokens.extend(_tokenize_issue_description(text))

    keywords = row.get("keywords")
    if isinstance(keywords, (list, tuple, set)):
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                tokens.extend(_tokenize_issue_description(keyword))

    structured_match = _infer_structured_category(row, tokens, context)
    scanner_label_map: Mapping[str, str] = context.get("scanner_labels", {}) if context else {}
    root_cause_label_map: Mapping[str, str] = context.get("root_cause_labels", {}) if context else {}
    scanner_model = ""
    for candidate in (
        row.get("scanner_model"),
        row.get("scanner"),
        row.get("scanner_type"),
        row.get("scanner_sn"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            scanner_model = candidate.strip()
            break

    root_cause_code = row.get("root_cause_code") or row.get("root_cause_id")
    if isinstance(root_cause_code, str):
        root_cause_code_display = root_cause_code.strip().upper()
    elif root_cause_code is not None:
        root_cause_code_display = str(root_cause_code)
    else:
        root_cause_code_display = ""

    root_cause_text_norm = _normalize_text_field(row.get("root_cause"))
    root_cause_display = (
        root_cause_label_map.get(root_cause_text_norm)
        if root_cause_label_map
        else row.get("root_cause")
    )

    if structured_match:
        label, score = structured_match
        if root_cause_code_display:
            return f"{label} – {root_cause_code_display}"
        if scanner_model:
            return f"{label} – {scanner_model}"
        if recurrence_count >= 3:
            return f"{label} (Recurring)"
        return label

    inferred_category = _infer_report_category(row, tokens)
    if inferred_category:
        if recurrence_count >= 3:
            return f"{inferred_category} (Recurring)"
        return inferred_category

    if root_cause_code_display:
        return f"Root Cause – {root_cause_code_display}"

    if scanner_model:
        scanner_norm = _normalize_text_field(scanner_model)
        display = scanner_label_map.get(scanner_norm, scanner_model)
        return f"Scanner – {display}"

    if recurrence_count >= 3:
        if isinstance(root_cause_display, str) and root_cause_display.strip():
            return f"Recurring – {_summarize_text(root_cause_display, width=40)}"
        return "Recurring Issue"

    if tokens:
        top_tokens: list[str] = []
        for token, _ in Counter(tokens).most_common():
            if token not in top_tokens:
                top_tokens.append(token)
            if len(top_tokens) >= 2:
                break
        if top_tokens:
            return " / ".join(token.title() for token in top_tokens)

    if isinstance(root_cause_display, str) and root_cause_display.strip():
        return _summarize_text(root_cause_display, width=40)

    if text_candidates:
        return _summarize_text(text_candidates[0], width=40)

    return "General"
