"""Reader for Tray files (``.trayitem`` + ``.householdbinary``)."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Optional

from ..catalog.models import Catalog
from .models import SavedSim, TrayHousehold, TrayItem, TrayLibrary
from .protobuf import ProtobufError, decode
from .reader import sim_from_dict, _as_list
from .schema import SCHEMAS

__all__ = [
    "TrayError",
    "read_tray_item",
    "read_household_binary",
    "read_tray_library",
    "pair_key",
]


class TrayError(ValueError):
    """Raised when a Tray file cannot be parsed."""


def read_tray_item(path: str | Path) -> TrayItem:
    """Read a ``.trayitem`` metadata file."""
    path = Path(path)
    data = path.read_bytes()
    if len(data) < 8:
        raise TrayError(f"{path.name}: file is too small")
    _version, length = struct.unpack_from("<II", data, 0)
    payload = data[8 : 8 + length] if 0 < length <= len(data) - 8 else data[8:]
    try:
        raw = decode(payload, "TrayItem", SCHEMAS)
    except ProtobufError as exc:
        raise TrayError(f"{path.name}: {exc}") from exc

    nested = raw.get("data", {}) or {}
    return TrayItem(
        path=path,
        item_id=raw.get("item_id"),
        item_type=raw.get("item_type"),
        hash=raw.get("hash"),
        title=raw.get("title"),
        description=raw.get("description"),
        creator=raw.get("creator"),
        timestamp=raw.get("timestamp"),
        raw=raw,
    )


def read_household_binary(
    path: str | Path,
    catalog: Optional[Catalog] = None,
) -> TrayHousehold:
    """Read a ``.householdbinary`` file into a :class:`TrayHousehold`."""
    path = Path(path)
    data = path.read_bytes()
    raw = None
    last_error: Optional[Exception] = None
    # The normal container header is 16 bytes; tolerate variants.
    for offset in (16, 12, 8, 0):
        if offset >= len(data):
            continue
        try:
            candidate = decode(data[offset:], "FamilyData", SCHEMAS)
        except ProtobufError as exc:
            last_error = exc
            continue
        if candidate.get("family_account") is not None:
            raw = candidate
            break
    if raw is None:
        raise TrayError(f"{path.name}: could not decode FamilyData ({last_error})")

    family = raw.get("family_account", {}) or {}
    raw_sims = _as_list(family.get("sim"))
    names: dict[int, str] = {}
    for sim in raw_sims:
        sim_id = sim.get("sim_id")
        if sim_id:
            names[sim_id] = f"{sim.get('first_name', '')} {sim.get('last_name', '')}".strip()
    sims = [sim_from_dict(sim, catalog, names) for sim in raw_sims if sim.get("sim_id")]

    return TrayHousehold(
        path=path,
        family_name=family.get("familyname"),
        description=family.get("description") or family.get("hashtag_description"),
        money=family.get("money"),
        home_zone=family.get("familyzoneid") or raw.get("homezone_id"),
        last_played_sim_id=raw.get("lastplayed_simid"),
        hashtag_description=family.get("hashtag_description"),
        sims=sims,
        raw=raw,
    )


def pair_key(path: Path) -> str:
    """Return the shared ID between a ``.trayitem`` and ``.householdbinary``."""
    return path.stem.split("!")[-1]


def read_tray_library(
    folder: str | Path,
    catalog: Optional[Catalog] = None,
) -> TrayLibrary:
    """Read every Tray item/household in a Tray folder."""
    folder = Path(folder)
    items: dict[str, TrayItem] = {}
    households: list[TrayHousehold] = []

    for path in sorted(folder.glob("*.trayitem")):
        try:
            item = read_tray_item(path)
        except TrayError:
            continue
        items[pair_key(path)] = item

    for path in sorted(folder.glob("*.householdbinary")):
        try:
            household = read_household_binary(path, catalog)
        except TrayError:
            continue
        household.item = items.get(pair_key(path))
        households.append(household)

    return TrayLibrary(items=list(items.values()), households=households)
