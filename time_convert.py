from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from parsing import TimeCandidate


_TIMEZONES: Dict[str, Dict] = {}
_OVERRIDES: List[Dict] = []
_ALIAS_TO_OVERRIDE: Dict[str, Dict] = {}


@dataclass
class ResolvedTimezone:
    code: str
    offset_hours: int
    extra_minutes: int = 0  # for half-hour / quarter-hour offsets


def load_timezone_data() -> None:
    """
    Load timezone and override data from JSON files on disk.
    """
    global _TIMEZONES, _OVERRIDES, _ALIAS_TO_OVERRIDE

    base = Path(__file__).parent

    tz_path = base / "timezones.json"
    overrides_path = base / "timezone_overrides.json"

    with tz_path.open("r", encoding="utf-8") as f:
        tz_list = json.load(f)

    _TIMEZONES = {entry["value"]: entry for entry in tz_list}

    with overrides_path.open("r", encoding="utf-8") as f:
        _OVERRIDES = json.load(f)

    alias_map: Dict[str, Dict] = {}
    for override in _OVERRIDES:
        for key in override.get("keys", []):
            alias_map[key.lower()] = override
    _ALIAS_TO_OVERRIDE = alias_map


def _parse_extra_minutes(dst_value: str) -> int:
    """
    Parse DST strings of the form '+:30 (...)' or '+:45 (...)' into minutes.
    Returns 0 if not applicable.
    """
    dst_value = dst_value.strip()
    if not dst_value.startswith("+:"):
        return 0
    try:
        minutes_str = dst_value[2:4]
        return int(minutes_str)
    except Exception:
        return 0


def resolve_alias(alias: str) -> Optional[ResolvedTimezone]:
    """
    Resolve a free-form alias like 'pst', 'london', or 'utc+2' into a ResolvedTimezone.
    """
    if not alias:
        return None

    alias_norm = alias.strip().lower()

    # Try exact override key match first.
    override = _ALIAS_TO_OVERRIDE.get(alias_norm)
    if override is not None:
        code = str(override.get("timezone", "")).strip()
        offset_hours: Optional[int] = override.get("offset")

        if offset_hours is None:
            tz_entry = _TIMEZONES.get(code)
            if tz_entry is None:
                return None
            offset_hours = int(tz_entry.get("offset", 0))

        extra_minutes = _parse_extra_minutes(str(override.get("dst", "")))
        return ResolvedTimezone(code=code, offset_hours=int(offset_hours), extra_minutes=extra_minutes)

    # Try to match against timezone labels if no override was found.
    for code, entry in _TIMEZONES.items():
        label = str(entry.get("label", "")).lower()
        if alias_norm in label:
            return ResolvedTimezone(code=code, offset_hours=int(entry.get("offset", 0)))

    # Handle raw UTC offsets like 'utc+2', 'utc-5', 'gmt+1', etc.
    for prefix in ("utc", "gmt"):
        if alias_norm.startswith(prefix):
            rest = alias_norm[len(prefix) :]
            try:
                offset_hours = int(rest)
                return ResolvedTimezone(code=f"{prefix}{offset_hours}", offset_hours=offset_hours)
            except ValueError:
                # Maybe the rest looks like '+2' or '-5'
                try:
                    offset_hours = int(rest.replace("+", ""))
                    return ResolvedTimezone(code=f"{prefix}{offset_hours}", offset_hours=offset_hours)
                except ValueError:
                    pass

    return None


def resolve_timezone_choice(user_input: str) -> Optional[str]:
    """
    Resolve a user-provided timezone string for the /timely command into a canonical code.
    """
    if not user_input:
        return None

    # Try alias resolution first.
    resolved = resolve_alias(user_input)
    if resolved is not None:
        return resolved.code

    # Try matching against the short codes (X, W, V, etc.).
    code = user_input.strip().upper()
    if code in _TIMEZONES:
        return code

    # Try partial matches on labels.
    user_norm = user_input.strip().lower()
    for tz_code, entry in _TIMEZONES.items():
        label = str(entry.get("label", "")).lower()
        if user_norm in label:
            return tz_code

    return None


def _parse_time_of_day(time_text: str, now_local: datetime) -> Optional[tuple[int, int]]:
    """
    Parse a time string like '8:00p', '8pm', '13:00', or '1300' into (hour24, minute).
    Uses a simple heuristic to infer AM/PM for 12-hour times without an explicit suffix.
    """
    s = time_text.strip().lower()

    # Detect and strip am/pm information.
    ampm = None
    if "am" in s or "pm" in s:
        # Prefer explicit 'am' / 'pm'.
        if "am" in s:
            ampm = "am"
            s = s.replace("am", "")
        if "pm" in s:
            ampm = "pm"
            s = s.replace("pm", "")
    else:
        # Single-letter suffixes like '8p' or '8a'.
        if s.endswith("a"):
            ampm = "am"
            s = s[:-1]
        elif s.endswith("p"):
            ampm = "pm"
            s = s[:-1]

    s = s.strip()

    hour: int
    minute: int

    if ":" in s or "." in s:
        sep = ":" if ":" in s else "."
        parts = s.split(sep, 1)
        if len(parts) != 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return None
    elif s.isdigit() and len(s) in (3, 4):
        # 3-4 digit compact time, e.g. 800 or 1300 -> HHMM
        if len(s) == 3:
            hour = int(s[0])
            minute = int(s[1:])
        else:
            hour = int(s[:2])
            minute = int(s[2:])
    elif s.isdigit():
        # Hour only, e.g. '8'
        hour = int(s)
        minute = 0
    else:
        return None

    # Normalize based on AM/PM.
    if ampm == "pm":
        if 1 <= hour <= 11:
            hour += 12
    elif ampm == "am":
        if hour == 12:
            hour = 0

    # If no am/pm was provided and this looks like a 12-hour time, use a
    # simple heuristic based on the current local hour (similar idea to timely-bot).
    if ampm is None and 1 <= hour <= 12:
        cur = now_local.hour
        # Rough heuristic: choose the interpretation that is "next" relative to now.
        if cur % 12 > hour:
            # We've already passed this hour in the current half of the day.
            # Flip AM/PM relative to now.
            if cur >= 12:
                # Currently PM, so treat this as AM of next cycle.
                hour = hour  # 1-11 stay as AM, 12 -> 0 handled above if needed.
            else:
                # Currently AM, treat as PM.
                if hour != 12:
                    hour += 12
        else:
            # Not yet reached this hour in the current half of the day.
            if cur >= 12:
                # Currently PM, keep as PM.
                if hour != 12:
                    hour += 12
            else:
                # Currently AM, keep as AM (no change).
                pass

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return hour, minute


def _resolved_for_user(zone_text: Optional[str], user_tz_code: Optional[str]) -> Optional[ResolvedTimezone]:
    """
    Resolve the timezone for a candidate, preferring explicit zone text, then
    falling back to the user's stored timezone code.
    """
    if zone_text:
        resolved = resolve_alias(zone_text)
        if resolved is not None:
            return resolved

    if user_tz_code:
        entry = _TIMEZONES.get(user_tz_code)
        if entry is not None:
            return ResolvedTimezone(
                code=user_tz_code,
                offset_hours=int(entry.get("offset", 0)),
                extra_minutes=0,
            )

    return None


def compute_unix_timestamp_for_candidate(
    candidate: TimeCandidate,
    user_tz_code: Optional[str],
    now_utc: Optional[datetime] = None,
) -> Optional[int]:
    """
    Convert a TimeCandidate into a UNIX timestamp suitable for Discord's <t:...> syntax.

    Returns None if no valid timezone can be resolved or the time string is invalid.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    resolved_tz = _resolved_for_user(candidate.zone_text, user_tz_code)
    if resolved_tz is None:
        return None

    # Compute the current local time in the resolved timezone.
    offset_delta = timedelta(hours=resolved_tz.offset_hours, minutes=resolved_tz.extra_minutes)
    now_local = now_utc + offset_delta

    parsed = _parse_time_of_day(candidate.time_text, now_local=now_local)
    if parsed is None:
        return None

    hour, minute = parsed

    # Use today's date in the resolved timezone.
    local_date = now_local.date()
    local_dt = datetime(
        year=local_date.year,
        month=local_date.month,
        day=local_date.day,
        hour=hour,
        minute=minute,
        tzinfo=timezone(offset_delta),
    )

    # Convert to UTC.
    utc_dt = local_dt.astimezone(timezone.utc)
    return int(utc_dt.timestamp())

