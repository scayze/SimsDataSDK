"""Discover shared skill XP thresholds from module-level game tuning.

The game stores the XP needed for each successive level in
``statistics.skill.Skill.SKILL_LEVEL_LIST``.  Tuning skill definitions select a
row by ``skill_level_type``.  This reader never infers that type from names.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import accumulate
from typing import Iterable, Optional
from xml.etree.ElementTree import Element

from .catalog.diagnostics import ExtractionIssue
from .core import COMBINED_TUNING_TYPE_ID, TUNING_TYPE_ID, CombinedTuning, DBPF, ResourceKey
from .export import Serializable
from .installation import PackageInfo
from .skills import SkillCurve, SkillCurveError

__all__ = ["SkillCurveDiscovery", "discover_skill_curves"]


@dataclass
class SkillCurveDiscovery(Serializable):
    """Discovered level types and their source, with any scan failures.

    An incomplete scan can have missed a later override; by default
    :meth:`for_skill` refuses to select a curve in that situation. A complete
    scan only means supported resources were read successfully; it does not
    rule out changes in unsupported formats or script mods.
    """

    curves: dict[str, SkillCurve] = field(default_factory=dict)
    package_path: Optional[str] = None
    resource_key: Optional[ResourceKey] = None
    diagnostics: list[ExtractionIssue] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.diagnostics

    def for_skill(self, skill: object, *, allow_incomplete: bool = False) -> Optional[SkillCurve]:
        """Resolve an explicit catalog skill's level type, or return ``None``."""
        if not self.complete and not allow_incomplete:
            return None
        if getattr(skill, "is_skill", None) is not True:
            return None
        level_type = getattr(skill, "skill_level_type", None)
        return self.curves.get(level_type) if level_type else None

    def to_dict(self, **options) -> dict:
        return {"curves": {k: v.to_dict() for k, v in self.curves.items()},
                "package_path": self.package_path,
                "resource_key": str(self.resource_key) if self.resource_key else None,
                "complete": self.complete,
                "diagnostics": [issue.to_dict(**options) for issue in self.diagnostics]}


def _resolve(ct: CombinedTuning, node: Optional[Element]) -> Optional[Element]:
    for _ in range(32):
        if node is None or node.tag != "r":
            return node
        node = ct.references.resolve(node)
    raise SkillCurveError("cyclic or deeply nested tuning reference")


def _field(node: Element, name: str) -> Optional[Element]:
    return next((child for child in node if child.get("n") == name), None)


def _extract_table(ct: CombinedTuning, source: str) -> Optional[dict[str, SkillCurve]]:
    module = ct.find_module("statistics.skill")
    if module is None:
        return None
    skill_class = next((child for child in module if child.tag == "C" and child.get("n") == "Skill"), None)
    table = _resolve(ct, _field(skill_class, "SKILL_LEVEL_LIST")) if skill_class is not None else None
    if table is None:
        return None
    if table.tag != "L":
        raise SkillCurveError("SKILL_LEVEL_LIST is not a list")
    curves: dict[str, SkillCurve] = {}
    for row_ref in table:
        row = _resolve(ct, row_ref)
        key = _resolve(ct, _field(row, "key")) if row is not None else None
        values = _resolve(ct, _field(row, "value")) if row is not None else None
        name = (key.text or "").strip() if key is not None else ""
        if not name or name in curves or values is None or values.tag != "L":
            raise SkillCurveError("invalid or duplicate skill level type")
        increments: list[float] = []
        for item in values:
            value = _resolve(ct, item)
            try:
                amount = float(value.text) if value is not None and value.text else float("nan")
            except ValueError:
                amount = float("nan")
            if not math.isfinite(amount) or amount <= 0:
                raise SkillCurveError(f"invalid XP amount for level type {name}")
            increments.append(amount)
        curves[name] = SkillCurve(name, tuple(accumulate(increments)), source)
    if not curves:
        raise SkillCurveError("empty SKILL_LEVEL_LIST")
    return curves


def discover_skill_curves(packages: Iterable[PackageInfo]) -> SkillCurveDiscovery:
    """Scan ordered packages for the shared skill table; later tables win.

    As in the catalog reader, individual tuning is considered before combined
    tuning within a package. This deterministic SDK policy is not a guarantee of
    the game's effective mod load order. Only the SDK's combined-tuning and
    standard tuning resource types are read; other class-hashed mod resources
    and script changes are not detected. Unreadable resources are diagnosed.
    """
    result = SkillCurveDiscovery()
    for info in packages:
        try:
            package = DBPF(info.path)
            entries = list(package.iter_entries_for_types({TUNING_TYPE_ID, COMBINED_TUNING_TYPE_ID}))
        except Exception as exc:
            result.diagnostics.append(ExtractionIssue.from_exception(
                "skill_curve_package", exc, package_path=str(info.path), recoverable=True))
            continue
        entries.sort(key=lambda entry: entry.key.type_id == COMBINED_TUNING_TYPE_ID)
        for entry in entries:
            if entry.is_null:
                continue
            try:
                data = DBPF.read_entry(info.path, entry)
                if entry.key.type_id == TUNING_TYPE_ID:
                    raw = data.decode("utf-8-sig", errors="replace")
                    try:
                        ct = CombinedTuning.from_xml(raw)
                    except Exception:
                        ct = CombinedTuning.from_xml(f"<root>{raw}</root>")
                else:
                    ct = CombinedTuning.parse(data)
                curves = _extract_table(ct, f"{info.path} ({entry.key})")
                if curves is not None:
                    result.curves = curves
                    result.package_path = str(info.path)
                    result.resource_key = entry.key
            except Exception as exc:
                result.diagnostics.append(ExtractionIssue.from_exception(
                    "skill_curve_resource", exc, package_path=str(info.path),
                    resource_key=entry.key, recoverable=True))
    return result
