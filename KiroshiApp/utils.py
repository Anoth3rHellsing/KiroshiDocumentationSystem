import re
import math
import datetime
from datetime import datetime, date, timezone, time as datetime_time, timedelta
from pathlib import Path
import random
import calendar
import logging
import streamlit as st
import altair as alt
import pandas as pd
from typing import Iterable, Mapping, Sequence
from collections import Counter, defaultdict

# Helper to avoid circular import for coercing legacy mappings which might be called from data_manager
def _coerce_case_mapping(data: object) -> dict | None:
    """Return a dictionary representation from historical payloads."""
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        dict_items = [item for item in data if isinstance(item, dict)]
        if dict_items:
            from KiroshiApp.utils import _mapping_freshness_score, _select_latest_mapping
            return _select_latest_mapping(dict_items)
    return None

def _mapping_freshness_score(item: Mapping[str, object], position: int) -> float:
    """Score mapping recency based on last_modified and original position."""
    ts = None
    try:
        raw = item.get("last_modified")
        if isinstance(raw, str):
            ts = datetime.fromisoformat(raw).timestamp()
    except Exception:
        ts = None
    # Prefer valid timestamps; otherwise, prefer later positions in the list.
    if ts is None:
        return float(position)
    return ts


def _select_latest_mapping(items: list[Mapping[str, object]]) -> Mapping[str, object]:
    """Return the most recent mapping based on timestamp/position."""
    if len(items) == 1:
        return items[0]
    best_item = items[0]
    best_score = _mapping_freshness_score(best_item, 0)
    for idx, item in enumerate(items[1:], start=1):
        score = _mapping_freshness_score(item, idx)
        if score >= best_score:
            best_item, best_score = item, score
    return best_item

def normalize_priority(value) -> str:
    from KiroshiApp.constants import DEFAULT_TRACKING_PRIORITY, PRIORITY_OPTIONS
    if not value:
        return DEFAULT_TRACKING_PRIORITY
    if value not in PRIORITY_OPTIONS:
        return DEFAULT_TRACKING_PRIORITY
    return value

try:
    from KiroshiApp.constants import (
        ThemePalette, HOLIDAY_THEMES, DEFAULT_THEME,
        HOLIDAY_NAME_TO_KEY, SPECIAL_THEME_PERIODS,
        KIROSHI_MESSAGES, STREAMLIT_FONT_FALLBACK
    )
except ImportError:
    # Circular import fallback or bootstrap
    ThemePalette = None
    HOLIDAY_THEMES = {}
    DEFAULT_THEME = None
    HOLIDAY_NAME_TO_KEY = {}
    SPECIAL_THEME_PERIODS = []
    KIROSHI_MESSAGES = []
    STREAMLIT_FONT_FALLBACK = "sans-serif"

def sanitize_case_id(case_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", case_id.strip())
    return safe_id or "case"

def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename preserving extension when possible."""
    name = Path(filename).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return sanitized or "file"

def _format_utc_timestamp(value: datetime) -> str:
    """Serialize a :class:`datetime` to an ISO-8601 string with a ``Z`` suffix."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )

def _utc_now_z() -> str:
    """Return the current UTC time in ISO-8601 format with a ``Z`` suffix."""
    return _format_utc_timestamp(datetime.now(timezone.utc))

def _parse_utc_timestamp(value: object | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None

def _normalize_hardware_test_text(value: object) -> str:
    """Return a text representation for stored hardware test values."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return ""
    text = str(value).strip()
    return text

def _normalize_damage_classification(value: object) -> str:
    """Return a human readable scanner damage classification."""
    if value is None:
        return ""

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        normalized = text.lower()
        if normalized in {"accidental", "accidental damage", "y", "yes", "true", "1"}:
            return "Accidental damage"
        if normalized in {"internal", "internal damage", "n", "no", "false", "0", "none"}:
            return "Internal damage"
        return text

    if isinstance(value, bool):
        return "Accidental damage" if value else "Internal damage"

    if isinstance(value, (int, float)):
        return "Accidental damage" if value else "Internal damage"

    text = str(value).strip()
    return text if text else ""

def _normalize_text_field(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()

def _format_display_value(value: object) -> str:
    """Format a value for UI display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)

def _format_multiline(text: str) -> str:
    """Format multiline text for display, preserving line breaks."""
    if not text:
        return ""
    return text.strip()

def _format_timedelta_compact(delta: timedelta) -> str:
    """Return a compact string for a timedelta, e.g. '2h 15m'."""
    if not isinstance(delta, timedelta):
        return ""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return "-"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def _calculate_next_wellness_event(settings: Mapping[str, object], now: datetime) -> tuple[str, datetime_time, int] | None:
    """Determine the next wellness break based on the schedule."""
    now_dt = now
    if not settings.get("enabled"):
        return None
    schedule = settings.get("schedule")
    if not isinstance(schedule, Mapping):
        return None

    candidates = []
    current_time = now_dt.time()

    for key, time_str in schedule.items():
        if not isinstance(time_str, str):
            continue
        try:
            event_time = _time_str_to_time(time_str, fallback=datetime_time(0, 0))
            if event_time > current_time:
                candidates.append((key, event_time))
        except ValueError:
            continue

    if not candidates:
        return None

    next_key, next_time = min(candidates, key=lambda x: x[1])

    # Calculate minutes remaining
    # We combine today with event_time to get a datetime, then diff
    today_event = datetime.combine(now_dt.date(), next_time).replace(tzinfo=now_dt.tzinfo)
    diff = today_event - now_dt
    minutes_remaining = int(diff.total_seconds() / 60)

    return next_key, next_time, minutes_remaining

def _calculate_lunch_midpoint(settings: Mapping[str, object]) -> datetime_time | None:
    """Calculate the midpoint of the scheduled lunch break."""
    schedule = settings.get("schedule", {})
    if not isinstance(schedule, Mapping):
        return None

    lunch_start_str = schedule.get("lunch")
    if not lunch_start_str:
        return None

    start_time = _time_str_to_time(str(lunch_start_str), fallback=datetime_time(12, 30))
    # Assuming lunch is 60 mins as per defaults
    mid_minutes = start_time.minute + 30
    extra_hour, final_minute = divmod(mid_minutes, 60)
    final_hour = (start_time.hour + extra_hour) % 24

    return datetime_time(final_hour, final_minute)

def _cluster_case_titles(titles: list[str]) -> tuple[list[int], dict[int, str]]:
    """Group similar case titles into clusters."""
    # Simplified clustering: group by exact normalized string
    clusters = []
    cluster_map = {}
    seen = {}
    next_id = 0

    for title in titles:
        norm = _normalize_text_field(title)
        if not norm:
            clusters.append(-1)
            continue

        if norm in seen:
            clusters.append(seen[norm])
        else:
            seen[norm] = next_id
            cluster_map[next_id] = title # Use first occurrence as label
            clusters.append(next_id)
            next_id += 1

    return clusters, cluster_map

def _text_contains_bug(
    root_cause: object,
    solution: object,
    description: object = None,
    title: object = None,
) -> bool:
    """Detect if text fields imply a software bug."""
    keywords = {"bug", "defect", "patch", "hotfix", "jira", "known issue"}
    combined = " ".join(
        _normalize_text_field(v)
        for v in (root_cause, solution, description, title)
        if v
    )
    return any(kw in combined for kw in keywords)

def _derive_analysis_label(row: pd.Series, context: dict) -> str:
    """Derive a high-level label for a case row."""
    # Check root cause map
    root_norm = str(row.get("root_cause_norm") or "")
    if root_norm and root_norm in context.get("root_cause_labels", {}):
        return context["root_cause_labels"][root_norm]

    # Fallback to title cluster
    return str(row.get("title_cluster_label") or "Unclassified")

def _coerce_int(value: object, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

def _shorten_for_log(text: str, limit: int = 160) -> str:
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"

def _summarize_text(text: str, width: int = 200) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    # simple truncation fallback if textwrap.shorten logic is complex or requires import
    # Re-implementing textwrap.shorten logic simply
    if len(cleaned) <= width:
        return cleaned
    return cleaned[:width-1] + "…"

WORD_PATTERN = re.compile(r"[A-Za-z0-9']+")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "from",
    "this",
    "have",
    "into",
    "will",
    "when",
    "case",
    "customer",
    "issue",
    "steps",
    "they",
    "their",
    "been",
    "were",
    "after",
    "before",
    "about",
    "also",
    "while",
    "should",
    "could",
    "there",
    "where",
    "using",
    "used",
    "need",
    "your",
    "each",
    "them",
    "than",
    "then",
    "once",
    "only",
    "very",
    "make",
    "made",
    "through",
    "over",
    "more",
    "less",
    "much",
    "many",
    "take",
    "taken",
    "back",
    "most",
    "some",
    "such",
    "same",
    "per",
    "upon",
    "done",
    "time",
}

def _extract_keywords(*texts: str) -> list[str]:
    keywords: list[str] = []
    for text in texts:
        if not text:
            continue
        tokens = WORD_PATTERN.findall(text.lower())
        for token in tokens:
            if len(token) <= 3 or token in STOPWORDS or token.isdigit():
                continue
            keywords.append(token)
    return sorted(set(keywords))

def _extract_json_object(block: str) -> dict[str, object] | None:
    if not isinstance(block, str):
        return None
    start = block.find("{")
    end = block.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    fragment = block[start : end + 1]
    try:
        return json.loads(fragment)
    except Exception:
        return None

def _disabled_tab_note() -> str:
    disabled_sections = []
    if not st.session_state.get("include_escalations", True):
        disabled_sections.append("Escalations tab")
    if not st.session_state.get("include_hardware", False):
        disabled_sections.append("Hardware issues tab")
    if not disabled_sections:
        return ""
    return (
        "The following tabs are disabled and should not be verified or referenced until they are turned on: "
        + ", ".join(disabled_sections)
        + ".\n\n"
    )

def _build_case_ai_dict(case) -> dict[str, object]:
    from dataclasses import asdict
    from KiroshiApp.constants import ESCALATION_TOGGLE_FIELDS, HARDWARE_TOGGLE_FIELDS
    case_dict = asdict(case)
    if not st.session_state.get("include_escalations", True):
        for field in ESCALATION_TOGGLE_FIELDS:
            case_dict.pop(field, None)
    if not st.session_state.get("include_hardware", False):
        for field in HARDWARE_TOGGLE_FIELDS:
            case_dict.pop(field, None)
    return case_dict

def format_tracking_date(value) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d")
    except Exception:
        return str(value)

def parse_iso_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None

def format_last_modified(value) -> str:
    parsed = parse_iso_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M")

def _time_str_to_time(value: str, *, fallback: datetime_time) -> datetime_time:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = max(0, min(23, int(hour_str)))
        minute = max(0, min(59, int(minute_str)))
        return datetime_time(hour=hour, minute=minute)
    except Exception:
        return fallback

def _time_to_string(value: datetime_time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"

def _normalize_wellness_settings(raw: object) -> dict[str, object]:
    from KiroshiApp.constants import DEFAULT_WELLNESS_SETTINGS
    base: dict[str, object] = {
        "enabled": False,
        "notification_lead": DEFAULT_WELLNESS_SETTINGS["notification_lead"],
        "schedule": dict(DEFAULT_WELLNESS_SETTINGS["schedule"]),
    }
    if isinstance(raw, Mapping):
        enabled = raw.get("enabled")
        if isinstance(enabled, bool):
            base["enabled"] = enabled
        lead = raw.get("notification_lead")
        if isinstance(lead, (int, float)):
            base["notification_lead"] = max(0, int(lead))
        schedule_raw = raw.get("schedule")
        if isinstance(schedule_raw, Mapping):
            for key in base["schedule"].keys():
                value = schedule_raw.get(key)
                if isinstance(value, str) and ":" in value:
                    base["schedule"][key] = value
    return base

def _normalize_text_value(value: object) -> str:
    """Return a safe string representation for widget-bound text fields."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("utf-8", "ignore")
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)

def _normalize_hex_color(value: str) -> str:
    """Return a normalized 6-digit hex color (prefixed with #)."""

    color = (value or "").strip().lstrip("#")
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in color):
        logging.debug("Received invalid hex color %r; defaulting to black", value)
        return "#000000"
    return f"#{color.lower()}"


def _hex_to_rgb_tuple(value: str) -> tuple[int, int, int]:
    color = _normalize_hex_color(value).lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _blend_hex_colors(base: str, mix: str, ratio: float) -> str:
    """Mix two colors together, clamping the ratio between 0 and 1."""

    ratio = min(max(ratio, 0.0), 1.0)
    base_rgb = _hex_to_rgb_tuple(base)
    mix_rgb = _hex_to_rgb_tuple(mix)
    blended = []
    for base_channel, mix_channel in zip(base_rgb, mix_rgb):
        value = round(base_channel * (1 - ratio) + mix_channel * ratio)
        blended.append(max(0, min(255, value)))
    return "#" + "".join(f"{channel:02x}" for channel in blended)


def _rgba(color: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb_tuple(color)
    alpha = min(max(alpha, 0.0), 1.0)
    alpha_str = f"{alpha:.3f}".rstrip("0").rstrip(".")
    return f"rgba({r}, {g}, {b}, {alpha_str})"


def _relative_luminance(color: str) -> float:
    """Return the W3C relative luminance for the provided hex color."""

    r, g, b = _hex_to_rgb_tuple(color)

    def _channel_luminance(channel: int) -> float:
        normalized = channel / 255
        if normalized <= 0.03928:
            return normalized / 12.92
        return ((normalized + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def _preferred_text_for_background(background: str, preferred: str) -> str:
    """Return a text color with adequate contrast for the given background."""

    background_luminance = _relative_luminance(background)
    preferred_luminance = _relative_luminance(preferred)

    if background_luminance >= 0.6 and preferred_luminance >= 0.55:
        return "#111827"
    if background_luminance <= 0.2 and preferred_luminance <= 0.35:
        return "#f8fafc"
    return preferred

def get_kiroshi_message(theme: object | None = None) -> str:
    """Return a pseudo-random Kiroshi message aligned with the active theme."""

    active_theme = theme or DEFAULT_THEME
    messages = getattr(active_theme, "glados_messages", KIROSHI_MESSAGES) if active_theme else KIROSHI_MESSAGES
    now = datetime.now()
    seed_key = getattr(active_theme, "key", "default") if active_theme else "default"
    seed = f"{seed_key}-{now.date().isoformat()}-{now.hour}"
    rng = random.Random(seed)
    return rng.choice(messages)


def _nth_weekday_of_month(year: int, month: int, weekday_index: int, occurrence: int) -> date:
    count = 0
    for day in range(1, 32):
        try:
            candidate = date(year, month, day)
        except ValueError:
            break
        if candidate.weekday() == weekday_index:
            count += 1
            if count == occurrence:
                return candidate
    raise ValueError("Invalid weekday occurrence")


def _last_weekday_of_month(year: int, month: int, weekday_index: int) -> date:
    for day in range(31, 0, -1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate.weekday() == weekday_index:
            return candidate
    raise ValueError("Invalid weekday for month")


def compute_us_holidays(year: int) -> list[tuple[date, str]]:
    holidays: list[tuple[date, str]] = [
        (date(year, 1, 1), "New Year's Day"),
        (date(year, 2, 8), "Day of Liberty"),
        (_nth_weekday_of_month(year, 1, calendar.MONDAY, 3), "Martin Luther King Jr. Day"),
        (_nth_weekday_of_month(year, 2, calendar.MONDAY, 3), "Presidents' Day"),
        (_last_weekday_of_month(year, 5, calendar.MONDAY), "Memorial Day"),
        (date(year, 6, 19), "Juneteenth National Independence Day"),
        (date(year, 7, 4), "Independence Day"),
        (_nth_weekday_of_month(year, 9, calendar.MONDAY, 1), "Labor Day"),
        (_nth_weekday_of_month(year, 10, calendar.MONDAY, 2), "Columbus Day"),
        (date(year, 11, 11), "Veterans Day"),
        (_nth_weekday_of_month(year, 11, calendar.THURSDAY, 4), "Thanksgiving Day"),
        (date(year, 12, 25), "Christmas Day"),
    ]
    return holidays


def _is_within_period(target: date, start_tuple: tuple[int, int], end_tuple: tuple[int, int]) -> bool:
    start = date(target.year, start_tuple[0], start_tuple[1])
    end = date(target.year, end_tuple[0], end_tuple[1])
    return start <= target <= end


def _holiday_theme_for_week(target: date) -> object | None:
    week_start = target - timedelta(days=target.weekday())
    week_end = week_start + timedelta(days=6)
    relevant_years = {week_start.year, week_end.year, target.year}
    holidays: list[tuple[date, str]] = []
    for year in relevant_years:
        holidays.extend(compute_us_holidays(year))
    week_holidays = [
        (holiday_date, name)
        for holiday_date, name in holidays
        if week_start <= holiday_date <= week_end
    ]
    if not week_holidays:
        return None
    week_holidays.sort(key=lambda item: item[0])
    if target < week_holidays[0][0]:
        key = HOLIDAY_NAME_TO_KEY.get(week_holidays[0][1])
        return HOLIDAY_THEMES.get(key, DEFAULT_THEME) if key else DEFAULT_THEME
    for holiday_date, name in week_holidays:
        if target <= holiday_date:
            key = HOLIDAY_NAME_TO_KEY.get(name)
            return HOLIDAY_THEMES.get(key, DEFAULT_THEME) if key else DEFAULT_THEME
    key = HOLIDAY_NAME_TO_KEY.get(week_holidays[-1][1])
    return HOLIDAY_THEMES.get(key, DEFAULT_THEME) if key else DEFAULT_THEME


def determine_active_theme(today: date | None = None) -> object:
    preview_key = st.session_state.get("theme_preview", "auto")
    if preview_key and preview_key != "auto":
        return HOLIDAY_THEMES.get(preview_key, DEFAULT_THEME)

    if st.session_state.get("dark_mode_enabled", False):
        from KiroshiApp.constants import DARK_THEME
        return DARK_THEME

    if not st.session_state.get("enable_holiday_theme", True):
        return DEFAULT_THEME

    current_day = today or date.today()
    for period in SPECIAL_THEME_PERIODS:
        if _is_within_period(current_day, period["start"], period["end"]):
            key = period["key"]
            return HOLIDAY_THEMES.get(key, DEFAULT_THEME)

    holiday_theme = _holiday_theme_for_week(current_day)
    return holiday_theme or DEFAULT_THEME


def apply_theme_palette(theme: object) -> None:
    if theme is None:
        return

    primary = getattr(theme, "primary", "#000000")
    accent = getattr(theme, "accent", "#000000")
    background = getattr(theme, "background", "#ffffff")
    surface = getattr(theme, "surface", "#ffffff")
    text = getattr(theme, "text", "#000000")
    muted_text = getattr(theme, "muted_text", "#000000")
    key = getattr(theme, "key", "default")

    primary_glow = _blend_hex_colors(primary, "#ffffff", 0.82)
    accent_glow = _blend_hex_colors(accent, "#ffffff", 0.8)
    surface_soft = _blend_hex_colors(surface, "#ffffff", 0.12)
    surface_muted = _blend_hex_colors(surface, background, 0.5)
    border_color = _blend_hex_colors(primary, "#000000", 0.35)
    chart_grid = _blend_hex_colors(text, background, 0.82)
    chart_axis = _blend_hex_colors(text, "#000000", 0.15)
    input_background = _blend_hex_colors(surface, background, 0.35)
    background_soft = _blend_hex_colors(background, surface, 0.25)
    card_shadow_color = _blend_hex_colors(background, "#000000", 0.6)
    button_shadow_color = _blend_hex_colors(primary, "#000000", 0.55)
    text_on_surface = _preferred_text_for_background(surface, text)
    text_on_white = _preferred_text_for_background("#ffffff", text)

    st.markdown(
        f"""
        <style>
        :root {{
            --kiroshi-primary: {primary};
            --kiroshi-accent: {accent};
            --kiroshi-background: {background};
            --kiroshi-surface: {surface};
            --kiroshi-text: {text};
            --kiroshi-muted: {muted_text};
            --kiroshi-surface-soft: {surface_soft};
            --kiroshi-surface-muted: {surface_muted};
            --kiroshi-border: {border_color};
            --kiroshi-primary-glow: {primary_glow};
            --kiroshi-accent-glow: {accent_glow};
            --kiroshi-chart-grid: {chart_grid};
            --kiroshi-chart-axis: {chart_axis};
            --kiroshi-input-background: {input_background};
            --kiroshi-text-on-surface: {text_on_surface};
            --kiroshi-text-on-white: {text_on_white};
        }}
        html, body {{
            background: {background};
            color: var(--kiroshi-text);
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
    _enable_altair_theme(theme)

def _enable_altair_theme(theme: object) -> None:
    primary = getattr(theme, "primary", "#000000")
    accent = getattr(theme, "accent", "#000000")
    background = getattr(theme, "background", "#ffffff")
    surface = getattr(theme, "surface", "#ffffff")
    text = getattr(theme, "text", "#000000")

    category_palette = [
        primary,
        accent,
        _blend_hex_colors(primary, accent, 0.4),
        _blend_hex_colors(accent, "#ffffff", 0.35),
        _blend_hex_colors(primary, "#ffffff", 0.45),
        _blend_hex_colors(accent, background, 0.2),
    ]
    sequential_palette = [
        _blend_hex_colors(primary, "#ffffff", ratio)
        for ratio in (0.85, 0.7, 0.5, 0.35, 0.2, 0.05)
    ]
    diverging_palette = [
        _blend_hex_colors(accent, "#ffffff", 0.55),
        accent,
        primary,
        _blend_hex_colors(primary, "#000000", 0.2),
    ]
    background_mix = _blend_hex_colors(background, surface, 0.35)
    chart_grid = _blend_hex_colors(text, background, 0.82)
    chart_axis = _blend_hex_colors(text, "#000000", 0.15)

    config = {
        "background": background_mix,
        "view": {"fill": background_mix, "stroke": "transparent"},
        "axis": {
            "labelColor": text,
            "titleColor": text,
            "domainColor": chart_axis,
            "tickColor": chart_axis,
            "gridColor": chart_grid,
        },
        "legend": {"labelColor": text, "titleColor": text},
        "title": {
            "color": text,
            "font": STREAMLIT_FONT_FALLBACK,
            "fontSize": 18,
            "fontWeight": 600,
        },
        "header": {"labelColor": text, "titleColor": text},
        "mark": {"color": primary, "fill": primary},
        "range": {
            "category": category_palette,
            "ordinal": category_palette,
            "diverging": diverging_palette,
            "heatmap": sequential_palette,
            "ramp": sequential_palette,
        },
    }

    if "kiroshi-active" not in alt.themes.names():
        alt.themes.register("kiroshi-active", lambda config=config: config)
    alt.themes.enable("kiroshi-active")

def merge_ai_learning_datasets(
    base_dataset: Mapping[str, object] | None,
    imported_dataset: Mapping[str, object],
    *,
    collaborator: str | None = None,
    local_signature: Iterable[tuple[str, float]] | None = None,
) -> dict[str, object] | None:
    if not isinstance(imported_dataset, Mapping):
        logging.error("Imported dataset is not a JSON object")
        return None

    base_cases = []
    if base_dataset and isinstance(base_dataset.get("cases"), list):
        base_cases = [dict(entry) for entry in base_dataset["cases"] if isinstance(entry, Mapping)]

    imported_cases_raw = imported_dataset.get("cases")
    if not isinstance(imported_cases_raw, list):
        logging.error("Imported dataset does not contain a cases list")
        return None
    imported_cases = [dict(entry) for entry in imported_cases_raw if isinstance(entry, Mapping)]

    combined: dict[tuple[str, str], dict[str, object]] = {}

    def _case_key(entry: Mapping[str, object]) -> tuple[str, str]:
        source = str(entry.get("source_path") or "").strip().lower()
        case_id = str(entry.get("case_id") or "").strip().lower()
        return source, case_id

    for entry in base_cases + imported_cases:
        key = _case_key(entry)
        if key in combined:
            existing = combined[key]
            try:
                existing_ts = float(existing.get("timestamp") or 0)
            except (TypeError, ValueError):
                existing_ts = 0.0
            try:
                new_ts = float(entry.get("timestamp") or 0)
            except (TypeError, ValueError):
                new_ts = 0.0
            if new_ts > existing_ts:
                combined[key] = dict(entry)
        else:
            combined[key] = dict(entry)

    if not combined:
        return None

    merged_sources: set[str] = set()
    if base_dataset:
        base_sources = base_dataset.get("merged_sources")
        if isinstance(base_sources, list):
            merged_sources.update(str(label) for label in base_sources if label)
        merged_sources.add("local")

    imported_sources = imported_dataset.get("merged_sources")
    if isinstance(imported_sources, list):
        merged_sources.update(str(label) for label in imported_sources if label)

    collaborator_label = collaborator or str(imported_dataset.get("shared_by") or "external").strip()
    if collaborator_label:
        merged_sources.add(collaborator_label)

    signature: Iterable[tuple[str, float]] | None = None
    if local_signature is not None:
        signature = local_signature
    elif base_dataset:
        base_signature = base_dataset.get("source_signature")
        if isinstance(base_signature, list):
            try:
                signature = tuple(tuple(item) for item in base_signature)
            except TypeError:
                signature = None
        elif isinstance(base_signature, tuple):
            signature = base_signature

    base_identity = None
    if base_dataset:
        candidate_identity = base_dataset.get("agent_identity")
        if isinstance(candidate_identity, Mapping):
            base_identity = dict(candidate_identity)
    if base_identity is None:
        candidate_identity = imported_dataset.get("agent_identity")
        if isinstance(candidate_identity, Mapping):
            base_identity = dict(candidate_identity)

    dataset = _create_ai_learning_dataset_from_cases(
        combined.values(),
        signature=signature,
        merged_sources=merged_sources,
        agent_identity=base_identity,
    )
    return dataset

def _normalize_agent_name(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""

def _create_ai_learning_dataset_from_cases(
    case_entries: Iterable[Mapping[str, object]],
    *,
    signature: Iterable[tuple[str, float]] | None = None,
    merged_sources: Iterable[str] | None = None,
    generated_at: str | None = None,
    agent_identity: Mapping[str, str] | None = None,
) -> dict[str, object] | None:
    cases: list[dict[str, object]] = []
    keyword_counter: Counter[str] = Counter()
    root_cause_counter: Counter[str] = Counter()
    solution_counter: Counter[str] = Counter()
    version_counter: Counter[str] = Counter()
    keyword_index: defaultdict[str, list[str]] = defaultdict(list)
    root_cause_cases: defaultdict[str, list[str]] = defaultdict(list)
    solution_cases: defaultdict[str, list[str]] = defaultdict(list)
    root_cause_labels: dict[str, str] = {}
    solution_labels: dict[str, str] = {}

    for entry in case_entries:
        if not isinstance(entry, Mapping):
            continue
        case_id = str(entry.get("case_id") or "").strip()
        if not case_id:
            continue
        title = str(entry.get("title") or "").strip()
        root_cause = str(entry.get("root_cause") or "").strip()
        solution = str(entry.get("solution") or "").strip()
        application_version = str(entry.get("application_version") or "").strip()
        keywords = entry.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = list(keywords)
        keywords = [str(keyword) for keyword in keywords if keyword]

        for keyword in keywords:
            keyword_counter[keyword] += 1
            if case_id not in keyword_index[keyword]:
                keyword_index[keyword].append(case_id)

        if root_cause:
            norm_root = root_cause.lower()
            root_cause_counter[norm_root] += 1
            root_cause_labels.setdefault(norm_root, root_cause)
            if case_id not in root_cause_cases[norm_root]:
                root_cause_cases[norm_root].append(case_id)

        if solution:
            norm_solution = solution.lower()
            solution_counter[norm_solution] += 1
            solution_labels.setdefault(norm_solution, solution)
            if case_id not in solution_cases[norm_solution]:
                solution_cases[norm_solution].append(case_id)

        if application_version:
            version_counter[application_version] += 1

        timestamp_raw = entry.get("timestamp")
        try:
            timestamp = float(timestamp_raw)
        except (TypeError, ValueError):
            timestamp = 0.0

        saved_at = entry.get("saved_at")
        if not saved_at and timestamp:
            saved_at = datetime.fromtimestamp(timestamp).isoformat()

        case_entry = {
            "case_id": case_id,
            "title": title or _summarize_text(entry.get("description", ""), width=120),
            "application_version": application_version,
            "root_cause": root_cause,
            "solution": solution,
            "solution_excerpt": entry.get("solution_excerpt")
            or _summarize_text(solution, width=260),
            "description_excerpt": entry.get("description_excerpt")
            or _summarize_text(entry.get("description", ""), width=260),
            "keywords": keywords,
            "timestamp": timestamp,
            "saved_at": saved_at,
            "source_path": entry.get("source_path"),
        }
        if agent_identity:
            agent_identifier = _normalize_agent_name(agent_identity.get("identifier"))
            if agent_identifier:
                case_entry["agent_id"] = agent_identifier
            display_name = _normalize_agent_name(agent_identity.get("display_name"))
            if display_name:
                case_entry["agent_name"] = display_name
        cases.append(case_entry)

    if not cases:
        return None

    cases.sort(key=lambda item: item.get("timestamp", 0), reverse=True)

    keyword_insights = [
        {
            "keyword": keyword,
            "count": count,
            "related_cases": keyword_index[keyword][:5],
        }
        for keyword, count in keyword_counter.most_common(20)
    ]

    root_cause_patterns = [
        {
            "root_cause": root_cause_labels[key],
            "count": root_cause_counter[key],
            "related_cases": root_cause_cases[key][:5],
        }
        for key in sorted(root_cause_counter, key=root_cause_counter.get, reverse=True)
    ]

    repeated_solutions = [
        {
            "solution": solution_labels[key],
            "count": solution_counter[key],
            "related_cases": solution_cases[key][:5],
        }
        for key in sorted(solution_counter, key=solution_counter.get, reverse=True)
        if solution_counter[key] > 1
    ]

    dataset: dict[str, object] = {
        "generated_at": generated_at or _utc_now_z(),
        "case_count": len(cases),
        "cases": cases,
        "keyword_insights": keyword_insights,
        "root_cause_patterns": root_cause_patterns,
        "repeated_solutions": repeated_solutions,
        "version_distribution": version_counter.most_common(),
        "insight_summary": {
            "top_keywords": [kw for kw, _ in keyword_counter.most_common(10)],
            "dominant_versions": version_counter.most_common(5),
        },
    }

    if signature is not None:
        dataset["source_signature"] = [list(item) for item in signature]

    merged_labels: set[str] = set()
    if merged_sources:
        merged_labels.update(str(label) for label in merged_sources if label)
    if merged_labels:
        dataset["merged_sources"] = sorted(merged_labels)

    if agent_identity:
        identity_payload = {
            "first_name": _normalize_agent_name(agent_identity.get("first_name")),
            "last_name": _normalize_agent_name(agent_identity.get("last_name")),
            "display_name": _normalize_agent_name(agent_identity.get("display_name")),
            "identifier": _normalize_agent_name(agent_identity.get("identifier")),
        }
        dataset["agent_identity"] = identity_payload
        if identity_payload.get("display_name") and not dataset.get("shared_by"):
            dataset["shared_by"] = identity_payload["display_name"]

    return dataset

from contextlib import contextmanager

@contextmanager
def safe_modal(title: str, key: str | None = None):
    """Provide a backwards-compatible context manager for Streamlit modals."""
    try:
        modal_callable = getattr(st, "modal")
    except AttributeError:
        modal_callable = None

    if callable(modal_callable):
        with modal_callable(title, key=key):
            yield
        return

    container = st.container()
    with container:
        st.markdown(f"### {title}")
        yield

from KiroshiApp.constants import LOG_FILE
from pathlib import Path
import os
import logging

def _collect_recent_logs(max_bytes: int = 65536) -> str:
    """Return the tail of the application log file for diagnostics."""
    synthetic_payload = os.environ.get("KIROSHI_SYNTHETIC_LOGS")
    if isinstance(synthetic_payload, str) and synthetic_payload:
        return synthetic_payload

    log_path = Path(LOG_FILE)
    # Check if absolute or relative. If relative, might be in APP_DIR/logs or root.
    # The setup logic in main app puts it in specific dirs.
    # We should search for it or assume it's where configured.
    # For now, let's look in cwd or APP_DIR/logs

    candidates = [
        Path.cwd() / LOG_FILE,
        Path(__file__).parent.parent.parent / "logs" / LOG_FILE,
        Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Kiroshi" / "logs" / LOG_FILE
    ]

    found_path = None
    for p in candidates:
        if p.exists():
            found_path = p
            break

    if not found_path:
        return "Log file not found."

    try:
        with found_path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(size - max_bytes, 0)
            handle.seek(start)
            if start > 0:
                handle.readline()
            return handle.read().strip()
    except OSError as exc:
        logging.error("Unable to read log file %s: %s", found_path, exc)
        return f"Unable to read logs: {exc}"

def global_widget_key(base: str) -> str:
    """Return a Streamlit widget key reserved for global (non-case) widgets."""
    key = f"global_{base}"
    # Simplified registration logic for this refactor
    # In legacy, it tracked collisions. Here we just return the key.
    return key

def render_responsive_altair_chart(chart: alt.Chart) -> None:
    """Render an Altair chart using the best available width argument."""
    # This helper was previously defined in views but is useful globally.
    import inspect
    try:
        _altair_signature = inspect.signature(st.altair_chart)
    except (TypeError, ValueError):
        _altair_signature = None

    ALTAIR_CHART_KWARGS = (
        {"width": "stretch"}
        if _altair_signature and "width" in _altair_signature.parameters
        else {}
    )
    st.altair_chart(chart, **ALTAIR_CHART_KWARGS)

def build_title(d) -> str:
    """Construct a helper string for case titles."""
    base = (
        f"|{d.company_name}|{d.subscription_id}|{d.brief_description}|"
        f"{d.application_version}|{d.case_id}|"
    )
    if st.session_state.get("second_line_mode") and d.straumann not in ("", "N/A"):
        return f"|{d.straumann}{base}"
    return base
