"""Helpers for loading themed QSS stylesheets."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


_MODE_PATTERN = re.compile(r"/\*\s*mode:(?P<mode>\w+)\s*\*/", re.IGNORECASE)


def _styles_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "styles.qss"


@lru_cache(maxsize=8)
def _load_sections() -> dict[str, str]:
    path = _styles_path()
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    matches = list(_MODE_PATTERN.finditer(content))
    if not matches:
        return {"all": content}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        mode = match.group("mode").lower()
        sections[mode] = content[start:end].strip()
    return sections


def load_stylesheet(mode: str = "system") -> str:
    """Return the QSS stylesheet for ``mode``.

    When ``mode`` is ``system`` or the file cannot be located, an empty string
    is returned so Qt falls back to its platform theme.
    """

    normalized = (mode or "system").lower()
    if normalized == "system":
        return ""
    sections = _load_sections()
    if not sections:
        return ""
    if normalized in sections:
        return sections[normalized]
    # Fall back to the first available section
    return next(iter(sections.values()))
