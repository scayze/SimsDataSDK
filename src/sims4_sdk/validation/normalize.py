"""Name normalization used by the wiki reconciler."""

from __future__ import annotations

import difflib
import re
import unicodedata

import mwparserfromhell

__all__ = [
    "clean_text",
    "normalize",
    "normalize_sim_name",
    "normalize_skill",
    "age_name",
    "gender_name",
    "names_match",
]

_DISAMBIGUATION = re.compile(r"\s*\([^)]*\)\s*$")


def clean_text(value: str | None) -> str:
    """Strip wiki markup and collapse whitespace."""
    if not value:
        return ""
    try:
        text = mwparserfromhell.parse(value).strip_code(normalize=True, collapse=True)
    except Exception:
        text = value
    return " ".join(text.split()).strip()


def normalize(value: str | None) -> str:
    """Return a comparison-friendly key (case, punctuation and spaces removed)."""
    text = clean_text(value)
    text = _DISAMBIGUATION.sub("", text)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.casefold().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_sim_name(value: str | None) -> str:
    text = clean_text(value)
    text = _DISAMBIGUATION.sub("", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.casefold().split())


def normalize_skill(value: str | None) -> str:
    """Normalize skill names across ``skill_`` / ``statistic_Skill_...`` forms."""
    text = normalize(value)
    for prefix in ("statisticskilladultmajor", "statisticskill", "skill"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text


def age_name(value: str | None) -> str | None:
    text = normalize(value)
    mapping = {
        "baby": "BABY",
        "infant": "INFANT",
        "toddler": "TODDLER",
        "child": "CHILD",
        "teen": "TEEN",
        "youngadult": "YOUNGADULT",
        "adult": "ADULT",
        "elder": "ELDER",
    }
    return mapping.get(text)


def gender_name(value: str | None) -> str | None:
    text = normalize(value)
    if text in ("male", "m"):
        return "MALE"
    if text in ("female", "f"):
        return "FEMALE"
    return None


def names_match(
    left: str | None,
    right: str | None,
    *,
    min_length: int = 4,
    fuzzy: bool = True,
    fuzzy_threshold: float = 0.9,
) -> bool:
    """True when two names are equal after normalization or one contains the other."""
    if not left or not right:
        return False
    left_parts = [normalize(part) for part in re.split(r"\s*/\s*", clean_text(left))]
    right_parts = [normalize(part) for part in re.split(r"\s*/\s*", clean_text(right))]
    a = normalize(left)
    b = normalize(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        if min(len(a), len(b)) >= min_length:
            return True
    for left_part in left_parts:
        for right_part in right_parts:
            if left_part and right_part and left_part == right_part:
                return True
            if left_part and right_part and min(len(left_part), len(right_part)) >= min_length:
                if left_part in right_part or right_part in left_part:
                    return True
    if fuzzy and abs(len(a) - len(b)) <= 4:
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        if ratio >= fuzzy_threshold:
            return True
    return False
