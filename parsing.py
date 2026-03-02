import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TimeCandidate:
    """
    A single time expression found in a message.

    - original_text: the exact substring from the message (used for display).
    - time_text: the portion that represents the time itself (e.g. '8:00p').
    - zone_text: any following zone/location text (e.g. 'PST', 'London', '(Vancouver)').
    """
    original_text: str
    time_text: str
    zone_text: Optional[str]


_TIME_PATTERN = re.compile(
    r"""
    (?P<prefix>[`"'*])?                # optional leading wrapper
    (?P<time>
        (?:[0-1]?\d|2[0-3])            # hour (0-23 or 1-12)
        (?:
            [:.][0-5]\d               # optional :mm or .mm
        )?
        \s*
        (?:[ap]m?)?                   # optional a/pm or am/pm (8p, 8pm, 8:00pm)
        |
        \d{3,4}                       # or compact 3-4 digit time like 800, 1300
    )
    (?P<suffix>[`"'])?                # optional closing quote/backtick (not star)
    (?:                               # optional timezone/location
        \s*
        (?:
            \((?P<zone_paren>[^)]+)\) # zone in parentheses, e.g. (London)
          | (?P<zone_word>[A-Za-z][A-Za-z0-9+\- ]*)
        )
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_time_candidates(message: str) -> List[TimeCandidate]:
    """
    Find all time expressions in a message.

    Supports variants such as:
      - 8:00p
      - "8:00a"
      - '8:00a'
      - *8:00a
      - 8:00p PST
      - 13:00 UTC
      - 1AM (London)
    """
    candidates: List[TimeCandidate] = []

    for match in _TIME_PATTERN.finditer(message):
        original = match.group(0)
        time_text = match.group("time")
        zone_paren = match.group("zone_paren")
        zone_word = match.group("zone_word")
        zone_text = zone_paren or zone_word

        # Clean up the time text a bit (strip outer whitespace).
        if time_text:
            time_text = time_text.strip()

        if not time_text:
            continue

        candidates.append(
            TimeCandidate(
                original_text=original,
                time_text=time_text,
                zone_text=zone_text.strip() if zone_text else None,
            )
        )

    return candidates

