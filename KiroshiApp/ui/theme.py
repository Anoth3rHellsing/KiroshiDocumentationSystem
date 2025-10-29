"""Helpers for loading themed QSS stylesheets."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


_MODE_PATTERN = re.compile(r"/\*\s*mode:(?P<mode>\w+)\s*\*/", re.IGNORECASE)
_BASE_SECTION_KEYS = ("shared", "common", "base", "all")


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
    sections = _load_sections()
    if not sections:
        return ""

    shared_sections = [sections[key] for key in _BASE_SECTION_KEYS if key in sections]
    themed_sections = {
        key: value
        for key, value in sections.items()
        if key not in _BASE_SECTION_KEYS
    }

    if not themed_sections:
        if shared_sections:
            return "\n\n".join(shared_sections).strip()
        return next(iter(sections.values())).strip()

    if normalized in {"", "system"}:
        normalized = "light" if "light" in themed_sections else ""

    stylesheet = themed_sections.get(normalized)
    if stylesheet is None:
        for fallback in ("light", "dark"):
            if fallback in themed_sections:
                stylesheet = themed_sections[fallback]
                break
    if stylesheet is None:
        stylesheet = next(iter(themed_sections.values()))

    sections_to_join = [part.strip() for part in (*shared_sections, stylesheet) if part]
    return "\n\n".join(sections_to_join)
