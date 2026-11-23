"""Read Tray metadata and discover household and lot file groups."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ..catalog.models import Catalog
from ..export import Serializable
from .artwork import Artwork, read_tray_image
from .models import SavedSim, TrayHousehold, TrayItem, TrayLibrary
from .reader import sim_from_dict, _as_list, _link_pet_ownership
from .tray_source import TrayError, TraySource, extract_tray_item, extract_household_binary
from .tray_summary import TrayHouseholdSummary, read_household_summary

__all__ = [
    "TrayError",
    "TraySource", "extract_tray_item", "extract_household_binary",
    "resolve_tray_item", "resolve_household_binary",
    "read_tray_item",
    "read_household_binary",
    "read_tray_library",
    "pair_key",
    "TrayListingGroup",
    "TrayListing",
    "list_tray_households",
    "TrayLot",
    "TrayLotListing",
    "list_tray_lots",
]


def resolve_tray_item(source: TraySource) -> TrayItem:
    if source.kind != "item":
        raise TrayError("expected a Tray item source")
    path = source.path
    raw = deepcopy(source.decoded)
    timestamp = raw.get("timestamp")
    if raw.get("item_type") == 2:
        timestamp = raw.get("household_id", timestamp)
    return TrayItem(
        path=path,
        item_id=raw.get("item_id"),
        item_type=raw.get("item_type"),
        hash=raw.get("hash"),
        title=raw.get("title"),
        description=raw.get("description"),
        creator=raw.get("creator"),
        timestamp=timestamp,
        raw=raw,
    )


def read_tray_item(path: str | Path) -> TrayItem:
    return resolve_tray_item(extract_tray_item(path))


@dataclass
class TrayLot(Serializable):
    """One lot in a Tray folder, with preview files in resource-group order."""

    identifier: str
    item: Optional[TrayItem] = None
    blueprint_files: list[Path] = field(default_factory=list)
    preview_files: list[Path] = field(default_factory=list)
    item_files: list[Path] = field(default_factory=list)
    width: Optional[int] = None
    depth: Optional[int] = None
    venue_id: Optional[int] = None
    venue_name_key: Optional[int] = None
    venue_name: Optional[str] = None

    def read_preview(self, index: int = 0) -> Artwork:
        """Decode an associated preview. Index zero selects the lowest group."""
        try:
            path = self.preview_files[index]
        except IndexError as exc:
            raise TrayError(f"no lot preview at index {index} for {self.identifier}") from exc
        return read_tray_image(path)


@dataclass
class TrayLotListing(Serializable):
    lots: list[TrayLot] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


def list_tray_lots(folder: str | Path, *, catalog: Optional[Catalog] = None) -> TrayLotListing:
    """Find lots by Tray identity without opening blueprints or preview images."""
    result = TrayLotListing()
    groups: dict[int, TrayLot] = {}
    candidates: list[tuple[int, int, Path]] = []
    for path in sorted(Path(folder).iterdir(), key=lambda path: path.name.casefold()):
        suffix = path.suffix.casefold()
        if suffix not in (".trayitem", ".blueprint", ".bpi") or not path.is_file():
            continue
        try:
            group_text, instance_text = path.stem.split("!")
            group, instance = int(group_text, 16), int(instance_text, 16)
            if not 0 <= group < 2**32 or not 0 < instance < 2**64:
                raise ValueError("Tray key outside supported range")
        except ValueError:
            if suffix != ".trayitem":
                result.errors.append({"path": str(path), "error": "invalid Tray resource filename"})
            continue
        candidates.append((instance, group, path))
        # Lot metadata has group 2. Keep incomplete groups visible.
        if suffix != ".trayitem" or group == 2:
            groups.setdefault(instance, TrayLot(identifier=f"0x{instance:016x}"))

    for instance, _, path in sorted(candidates):
        lot = groups.get(instance)
        if lot is None:
            continue
        suffix = path.suffix.casefold()
        if suffix == ".trayitem":
            lot.item_files.append(path)
        elif suffix == ".blueprint":
            lot.blueprint_files.append(path)
        else:
            lot.preview_files.append(path)

    for lot in sorted(groups.values(), key=lambda lot: lot.identifier):
        if len(lot.item_files) == 1:
            path = lot.item_files[0]
            try:
                item = read_tray_item(path)
                if item.item_type != 2:
                    raise TrayError("metadata does not describe a lot")
                metadata = item.raw.get("data", {}).get("blueprint", {})
                lot.item = item
                lot.width = metadata.get("size_x") or None
                lot.depth = metadata.get("size_z") or None
                lot.venue_id = metadata.get("venue_type") or None
                lot.venue_name_key = metadata.get("venue_type_string_key") or None
                if catalog is not None:
                    lot.venue_name = catalog.strings.get(lot.venue_name_key)
            except (TrayError, OSError) as exc:
                result.errors.append({"path": str(path), "error": str(exc)})
        for paths, label in ((lot.item_files, "metadata"), (lot.blueprint_files, "blueprint")):
            if len(paths) != 1:
                result.errors.append({"path": lot.identifier, "error": f"expected one {label} file, found {len(paths)}"})
        result.lots.append(lot)
    return result


def resolve_household_binary(source: TraySource, catalog: Optional[Catalog] = None) -> TrayHousehold:
    if source.kind != "household":
        raise TrayError("expected a Tray household source")
    path = source.path
    raw = deepcopy(source.decoded)

    family = raw.get("family_account", {}) or {}
    raw_sims = _as_list(family.get("sim"))
    names: dict[int, str] = {}
    for sim in raw_sims:
        sim_id = sim.get("sim_id")
        if sim_id:
            names[sim_id] = f"{sim.get('first_name', '')} {sim.get('last_name', '')}".strip()
    sims = [sim_from_dict(sim, catalog, names) for sim in raw_sims if sim.get("sim_id")]
    _link_pet_ownership({sim.sim_id: sim for sim in sims})

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


def read_household_binary(path: str | Path, catalog: Optional[Catalog] = None) -> TrayHousehold:
    return resolve_household_binary(extract_household_binary(path), catalog)


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
    summary: Optional[TrayHouseholdSummary] = None
    item: Optional[TrayItem] = None
    modified: Optional[float] = None


@dataclass
class TrayListing(Serializable):
    groups: list[TrayListingGroup] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    unmatched_images: list[Path] = field(default_factory=list)


def list_tray_households(folder: str | Path, *, lightweight: bool = False) -> TrayListing:
    """Discover groups without a catalog or loading images.

    With ``lightweight=True``, ``group.summary`` contains names and IDs, while
    ``group.household`` is None. Trackers and appearance are not decoded.
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
                if lightweight:
                    group.summary = read_household_summary(group.household_files[0])
                else:
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
            else:
                household = group.summary if lightweight else group.household
                if household:
                    matches.extend(group for sim in household.sims if sim.sim_id == image_id)
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
