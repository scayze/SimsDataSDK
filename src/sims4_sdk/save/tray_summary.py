"""Selective household metadata decoding for fast Tray listings.

Trackers and appearance payloads are deliberately not decoded.  The summary
types make that distinction explicit, rather than returning empty trackers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..export import Serializable
from .protobuf import ProtobufError, decode
from .schema import SCHEMAS


@dataclass
class TraySimSummary(Serializable):
    sim_id: int
    first_name: str = ""
    last_name: str = ""

    def to_dict(self, **options) -> dict:
        return {"sim_id": self.sim_id, "first_name": self.first_name, "last_name": self.last_name}


@dataclass
class TrayHouseholdSummary(Serializable):
    path: Path
    family_name: Optional[str] = None
    sims: list[TraySimSummary] = field(default_factory=list)

    def to_dict(self, **options) -> dict:
        return {"path": str(self.path), "family_name": self.family_name,
                "sims": [sim.to_dict() for sim in self.sims]}


# Reuse the actual schema definitions, but omit expensive nested Sim trackers.
# Unknown/unselected fields are skipped at the wire level without decoding.
_SUMMARY_SCHEMAS = {
    "FamilyData": {1: SCHEMAS["FamilyData"][1]},
    "AccountFamilyData": {tag: SCHEMAS["AccountFamilyData"][tag] for tag in (3, 6)},
    "SimData": {tag: SCHEMAS["SimData"][tag] for tag in (1, 5, 6)},
}


def read_household_summary(path: str | Path) -> TrayHouseholdSummary:
    """Read a household's name and Sim IDs/names without decoding trackers."""
    # The import is local because the listing module also imports this reader.
    from .tray import TrayError

    path = Path(path)
    data = path.read_bytes()
    last_error: Optional[Exception] = None
    for offset in (16, 12, 8, 0):
        if offset >= len(data):
            continue
        try:
            candidate = decode(data[offset:], "FamilyData", _SUMMARY_SCHEMAS)
        except ProtobufError as exc:
            last_error = exc
            continue
        if candidate.get("family_account") is None:
            continue
        family = candidate["family_account"]
        sims = [TraySimSummary(sim_id=sim["sim_id"],
                               first_name=sim.get("first_name", ""),
                               last_name=sim.get("last_name", ""))
                for sim in family.get("sim", []) if sim.get("sim_id")]
        return TrayHouseholdSummary(path=path, family_name=family.get("familyname"), sims=sims)
    raise TrayError(f"{path.name}: could not decode FamilyData ({last_error})")
