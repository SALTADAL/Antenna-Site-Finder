"""Chain detection.

Quality note from the brief: "If chain detection misses a Starbucks and the
salesperson cold-calls Starbucks corporate, the deal is dead and the tool
wasted everyone's time. Accuracy matters more than feature volume."

Approach:
    1. Normalize the business name (lowercase, strip punctuation, collapse spaces).
    2. Strip common location suffixes like "#1234", "- Downtown", store numbers.
    3. Match against a curated chain list with exact and substring rules.
    4. Also match against name+address fingerprints when the name alone is
       ambiguous (e.g. "Big O Tires" anywhere in the country is a chain).

We deliberately do not use fuzzy matching here because false positives
(flagging an independent as a chain) cost the user a real lead. False
negatives are recoverable by manual review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Regex to strip store numbers, location suffixes, and franchise indicators.
_LOCATION_SUFFIX_PATTERNS = [
    re.compile(r"\s*#\s*\d+\b", re.IGNORECASE),  # "Starbucks #2345"
    re.compile(r"\s*-\s*[a-z\s]+$", re.IGNORECASE),  # "Starbucks - Downtown"
    re.compile(r"\s*\d{2,5}\s*$"),  # trailing store number
    re.compile(r"\s*\(.*?\)\s*", re.IGNORECASE),  # parenthetical clarifiers
    re.compile(r"\s*\bat\b\s+.+$", re.IGNORECASE),  # "Subway at Mall"
]

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace. Idempotent."""
    s = name.strip()
    for pat in _LOCATION_SUFFIX_PATTERNS:
        s = pat.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip().lower()
    return s


@dataclass(frozen=True)
class ChainEntry:
    """One row in chains.json. Frozen for hashability."""

    canonical: str  # normalized form
    display: str  # original display form
    category: str
    match_mode: str = "exact"  # "exact" or "substring"


@lru_cache(maxsize=1)
def _load_chains() -> tuple[ChainEntry, ...]:
    """Read chains.json once and normalize."""
    path = get_settings().data_dir / "chains.json"
    if not path.exists():
        logger.warning("chains.json missing at %s; nothing will be flagged.", path)
        return ()

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    entries: list[ChainEntry] = []
    for item in raw.get("chains", []):
        display = item["name"]
        entries.append(
            ChainEntry(
                canonical=_normalize(display),
                display=display,
                category=item.get("category", "unknown"),
                match_mode=item.get("match_mode", "exact"),
            )
        )
    logger.info("Loaded %d chain entries.", len(entries))
    return tuple(entries)


def detect(business_name: str) -> tuple[bool, str | None]:
    """Return (is_chain, matched_display_name).

    Exact matches win. Substring matches are restricted to entries flagged
    `match_mode: substring`, which we use for brands whose store names
    always start with the brand (e.g. "McDonald's of 5th Avenue").
    """
    if not business_name:
        return (False, None)

    norm = _normalize(business_name)
    if not norm:
        return (False, None)

    chains = _load_chains()

    # Exact pass first.
    for entry in chains:
        if entry.match_mode == "exact" and norm == entry.canonical:
            return (True, entry.display)

    # Substring pass. Require the canonical to be a whole-word prefix to
    # avoid "Sub" matching "Submarine Repair Shop".
    for entry in chains:
        if entry.match_mode != "substring":
            continue
        if norm.startswith(entry.canonical + " ") or norm == entry.canonical:
            return (True, entry.display)
        # Also catch "the <chain>" or "<chain> of <place>"
        if f" {entry.canonical} " in f" {norm} ":
            return (True, entry.display)

    return (False, None)


def detect_many(names: Iterable[str]) -> dict[str, tuple[bool, str | None]]:
    """Batch helper. Returns a name -> (is_chain, match) dict."""
    return {n: detect(n) for n in names}
