"""Reader for Tray files (``.trayitem`` + ``.householdbinary``)."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..catalog.models import Catalog
from ..exceptions import Sims4SDKError
from ..export import Serializable
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
    "TrayListingGroup",
    "TrayListing",
    "list_tray_households",
]


class TrayError(Sims4SDKError, ValueError):
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


def _image_paths(folder: Path, extension: str, instance: int) -> list[Path]:
    matches = []
    for path in folder.glob(f"*.{extension}"):
        try:
            if int(pair_key(path), 0) == instance:
                matches.append(path)
        except ValueError:
            continue
    return sorted(matches)


def read_tray_library(
    folder: str | Path,
    catalog: Optional[Catalog] = None,
) -> TrayLibrary:
    """Read every Tray item/household in a Tray folder."""
    folder = Path(folder)
    items: dict[str, TrayItem] = {}
    households: list[TrayHousehold] = []
    errors: list[dict[str, str]] = []

    for path in sorted(folder.glob("*.trayitem")):
        try:
            item = read_tray_item(path)
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        items[pair_key(path)] = item

    for path in sorted(folder.glob("*.householdbinary")):
        try:
            household = read_household_binary(path, catalog)
        except Exception as exc:
            errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
            continue
        household.item = items.get(pair_key(path))
        households.append(household)

    return TrayLibrary(items=list(items.values()), households=households, errors=errors)


@dataclass
class TrayListingGroup(Serializable):
    """Files sharing a Tray identifier; duplicate files are kept visible."""

    identifier: str
    household_files: list[Path] = field(default_factory=list)
    item_files: list[Path] = field(default_factory=list)
    household_images: list[Path] = field(default_factory=list)
    sim_images: list[Path] = field(default_factory=list)
    household: Optional[TrayHousehold] = None
    item: Optional[TrayItem] = None
    modified: Optional[float] = None


@dataclass
class TrayListing(Serializable):
    groups: list[TrayListingGroup] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    unmatched_images: list[Path] = field(default_factory=list)


def list_tray_households(folder: str | Path) -> TrayListing:
    """Discover groups without a catalog or loading images.

    Ambiguous duplicate files are retained but not decoded. Sim portraits are
    associated by Sim ID, not by filename proximity or Sim name.
    """
    result = TrayListing()
    groups: dict[str, TrayListingGroup] = {}
    images: list[Path] = []
    for path in sorted(Path(folder).iterdir(), key=lambda p: p.name.casefold()):
        if not path.is_file():
            continue
        ext = path.suffix.casefold()
        if ext in (".sgi", ".hhi"):
            images.append(path)
        elif ext in (".householdbinary", ".trayitem"):
            key = pair_key(path).casefold()
            group = groups.setdefault(key, TrayListingGroup(identifier=key))
            (group.household_files if ext == ".householdbinary" else group.item_files).append(path)

    def failure(path: Path, exc: Exception) -> None:
        result.errors.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})

    for group in groups.values():
        for paths in (group.household_files, group.item_files):
            if len(paths) > 1:
                for path in paths:
                    failure(path, TrayError("ambiguous files with the same identifier"))
        for path in group.household_files + group.item_files:
            try:
                modified = path.stat().st_mtime
                group.modified = max(group.modified or modified, modified)
            except OSError as exc:
                failure(path, exc)
        if len(group.item_files) == 1:
            try:
                group.item = read_tray_item(group.item_files[0])
            except Exception as exc:
                failure(group.item_files[0], exc)
        if len(group.household_files) == 1:
            try:
                group.household = read_household_binary(group.household_files[0])
                group.household.item = group.item
            except Exception as exc:
                failure(group.household_files[0], exc)

    # Store portrait associations separately: their file ID is a Sim ID, not
    # the household group ID, and can be ambiguous across library entries.
    for path in images:
        try:
            image_id = int(pair_key(path), 0)
        except ValueError:
            result.unmatched_images.append(path)
            continue
        matches = []
        for group in groups.values():
            if path.suffix.casefold() == ".hhi":
                try:
                    if int(group.identifier, 0) == image_id:
                        matches.append(group)
                except ValueError:
                    pass
            elif group.household:
                matches.extend(group for sim in group.household.sims if sim.sim_id == image_id)
        if len(matches) == 1:
            if path.suffix.casefold() == ".hhi":
                matches[0].household_images.append(path)
            else:
                matches[0].sim_images.append(path)
            try:
                modified = path.stat().st_mtime
                matches[0].modified = max(matches[0].modified or modified, modified)
            except OSError as exc:
                failure(path, exc)
        else:
            result.unmatched_images.append(path)
            if len(matches) > 1:
                failure(path, TrayError("image matches multiple households"))
    result.groups = list(groups.values())
    return result
