"""Explicit skill XP curves and source-independent conversion.

Curve selection is deliberately the caller's responsibility.  Neither a
statistic's name nor its presence in a tracker proves which curve it uses.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from typing import Optional

from .exceptions import Sims4SDKError
from .export import Serializable

__all__ = [
    "SkillCurveError", "SkillCurve", "SkillProgress", "convert_skill_xp",
    "ADULT_CURVE", "CHILD_CURVE", "TODDLER_CURVE", "VAMPIRE_LORE_CURVE",
]


class SkillCurveError(Sims4SDKError, ValueError):
    """An invalid curve or XP value was supplied."""


@dataclass(frozen=True)
class SkillCurve(Serializable):
    """Inclusive XP threshold for each level, starting with level 1.

    ``source`` describes where the thresholds came from; it does not establish
    that this curve applies to any particular skill or game version.
    """

    name: str
    thresholds: tuple[float, ...]
    source: str

    def __post_init__(self) -> None:
        # Copy mutable inputs so a frozen instance stays immutable.
        object.__setattr__(self, "thresholds", tuple(self.thresholds))
        if (not self.thresholds or any(not isfinite(x) or x < 0 for x in self.thresholds)
                or any(a >= b for a, b in zip(self.thresholds, self.thresholds[1:]))):
            raise SkillCurveError("thresholds must be finite, non-negative and strictly increasing")

    @property
    def max_level(self) -> int:
        return len(self.thresholds)

    def to_dict(self, **options) -> dict:
        return {"name": self.name, "thresholds": list(self.thresholds), "source": self.source}


@dataclass(frozen=True)
class SkillProgress(Serializable):
    """A conversion result; ``assigned=None`` means assignment is unknown."""

    raw_xp: float
    level: Optional[int]
    curve: Optional[SkillCurve]
    assigned: Optional[bool]
    status: str

    def to_dict(self, **options) -> dict:
        return {"raw_xp": self.raw_xp, "level": self.level,
                "curve": self.curve.to_dict() if self.curve else None,
                "assigned": self.assigned, "status": self.status}


def convert_skill_xp(
    raw_xp: float, curve: Optional[SkillCurve] = None, *, assigned: Optional[bool] = None,
) -> SkillProgress:
    """Convert XP using an explicitly selected curve, retaining unknown states.

    Thresholds are inclusive and values above the last threshold are capped at
    the maximum level.  A value below the first threshold is unresolved.
    ``assigned=False`` suppresses a level; ``None`` retains uncertainty about
    assignment even when a numeric level can be calculated.
    """
    if not isfinite(raw_xp) or raw_xp < 0:
        raise SkillCurveError("XP must be finite and non-negative")
    if assigned is False:
        return SkillProgress(raw_xp, None, curve, assigned, "unassigned")
    if curve is None:
        return SkillProgress(raw_xp, None, None, assigned, "unresolved_curve")
    level = bisect_right(curve.thresholds, raw_xp)
    if level == 0:
        return SkillProgress(raw_xp, None, curve, assigned, "below_curve")
    return SkillProgress(raw_xp, level, curve, assigned, "resolved")


# Historical studio tables, calibrated against observed starter XP values.
# They are explicitly opt-in reference data, not verified for every game
# version or skill.  In particular, no tuning-name-based selection is made.
_REFERENCE = "Studio historical tables, calibrated from observed starter XP; not extracted from tuning"
ADULT_CURVE = SkillCurve("adult", (0, 1000, 3000, 5000, 9000, 15000, 25000, 40000, 60000, 80000), _REFERENCE)
CHILD_CURVE = SkillCurve("child", (0, 1000, 2000, 5000, 7500, 10000, 14000, 18000, 21000, 25000), _REFERENCE)
TODDLER_CURVE = SkillCurve("toddler", (0, 200, 500, 800, 1100), _REFERENCE)
VAMPIRE_LORE_CURVE = SkillCurve("vampire_lore", (0, 300, 1000, 2000, 3500, 5500, 8000, 11000, 15000, 20000, 26000, 33000, 41000, 50000, 60000), _REFERENCE)
