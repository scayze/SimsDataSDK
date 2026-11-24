"""Resolve installed lots and overlay current save zones by game identifiers."""

from __future__ import annotations

import struct
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.dbpf import DBPF, DBPFError, ResourceKey
from ..core.fnv import fnv1_32, fnv1_64
from ..core.lot_architecture import architecture_venue_id
from ..core.resource_types import (
    LOT_DESCRIPTION_TYPE_ID,
    REGION_DESCRIPTION_TYPE_ID,
    STREET_DESCRIPTION_TYPE_ID,
    WORLD_LOT_ARCHITECTURE_TYPE_ID,
)
from ..exceptions import Sims4SDKError
from ..export import Serializable
from ..paths import iter_pack_folders, iter_pack_root_folders

if TYPE_CHECKING:
    from ..installation import Installation
    from ..save.models import SaveFile
    from .static import StaticData
    from .worlds import LotRecord

__all__ = ["LotRegistry", "WorldLot"]


@dataclass(frozen=True)
class WorldLot(Serializable):
    """A selectable site or save zone with static identity and occupancy."""

    lot_id: int
    name: str | None = None
    region_id: int | None = None
    region_name: str | None = None
    street_id: int | None = None
    street_name: str | None = None
    world_id: int | None = None
    pack: str | None = None
    width: int | None = None
    depth: int | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    lot_description_id: int | None = None
    lot_template_id: int | None = None
    manifest_key: ResourceKey | None = None
    starter_household_id: int | None = None
    zone_id: int | None = None
    neighborhood_id: int | None = None
    household_id: int | None = None
    household_name: str | None = None
    occupancy: str = "unknown"
    #: Lot trait and challenge IDs: the new-save defaults in a clean registry,
    #: or the zone's current traits in a save overlay. None means unknown.
    lot_trait_ids: tuple[int, ...] | None = None

    @property
    def house_description_id(self) -> int | None:
        """The lot manifest instance, which keys default lot traits and thumbnails."""
        return self.manifest_key.instance if self.manifest_key is not None else None


@dataclass
class LotRegistry(Serializable):
    """Lots with region and street IDs suitable for grouping in a world picker."""

    lots: list[WorldLot] = field(default_factory=list)

    def lot(self, key: int | str) -> WorldLot | None:
        """Find a unique site by lot ID or exact case-insensitive name."""
        if isinstance(key, int):
            matches = [lot for lot in self.lots if lot.lot_id == key]
        else:
            matches = [lot for lot in self.lots if (lot.name or "").casefold() == key.casefold()]
        return matches[0] if len(matches) == 1 else None

    def find_lots(self, query: str = "", *, region_id: int | None = None,
                  street_id: int | None = None) -> list[WorldLot]:
        """Filter by lot name substring and/or exact region and street IDs."""
        needle = query.casefold()
        return [lot for lot in self.lots if needle in (lot.name or "").casefold()
                and (region_id is None or lot.region_id == region_id)
                and (street_id is None or lot.street_id == street_id)]

    def zone(self, zone_id: int) -> WorldLot | None:
        """Look up a zone in a registry with a save overlay."""
        return next((lot for lot in self.lots if lot.zone_id == zone_id), None)


def _street(data: bytes) -> tuple[int, str] | None:
    if len(data) < 28 or struct.unpack_from("<I", data)[0] != 11:
        return None
    region, length = struct.unpack_from("<QI", data, 16)
    if not 0 < length <= len(data) - 28:
        return None
    try:
        asset = data[28:28 + length].decode("ascii")
    except UnicodeDecodeError:
        return None
    if not asset.replace("_", "").replace("-", "").isalnum():
        return None
    return region, asset


def _world_packages(installation: Installation | None) -> dict[str, list[Path]]:
    if installation is None:
        return {}
    root = installation.install_dir
    folders = [root / "Data/Shared", *iter_pack_root_folders(root), *iter_pack_folders(root)]
    result: dict[str, list[Path]] = defaultdict(list)
    for folder in folders:
        for path in sorted((folder / "Worlds/Areas").glob("*.world")):
            result[path.stem.casefold()].append(path)
    return result


def _default_venue(path: Path, template: int, packages: dict[Path, DBPF]) -> int | None:
    try:
        if path not in packages:
            packages[path] = DBPF(path)
        package = packages[path]
        key = ResourceKey(WORLD_LOT_ARCHITECTURE_TYPE_ID, 0, fnv1_64(f"1-{template:08x}"))
        entry = package.find_entry(key)
        if entry is not None and not entry.is_null:
            data = package.read_resource(entry)
            if len(data) >= 4 and struct.unpack_from("<I", data)[0] == len(data) - 4:
                return architecture_venue_id(data[4:])
    except (DBPFError, OSError):
        return None
    return None


def _starter_occupancy(manifest: LotRecord | None) -> str:
    if manifest is None:
        return "unknown"
    if manifest.household_id:
        return "occupied"
    if manifest.household_assignment == bytes(16):
        return "vacant"
    return "unknown"


def build_lot_registry(static: StaticData, installation: Installation | None) -> LotRegistry:
    """Read default lot metadata for the installed game resources."""
    world = static.world
    if world is None:
        return LotRegistry()
    strings = static.catalog.strings
    geography = getattr(world, "geography", {})
    venue_names = getattr(world, "venue_names", {})
    initial_traits = getattr(static.catalog, "initial_lot_trait_ids", {})
    worlds = _world_packages(installation)
    packages: dict[Path, DBPF] = {}
    manifests: dict[int, list[tuple[ResourceKey, LotRecord]]] = defaultdict(list)
    for key, record in world.lot_resources.items():
        if record.lot_description_id:
            manifests[record.lot_description_id].append((key, record))

    lots = []
    for key, description in sorted(geography.items()):
        if key.type_id != LOT_DESCRIPTION_TYPE_ID or len(description) < 22:
            continue
        version, street_id, lot_id = struct.unpack_from("<IQI", description)
        if version != 12 or not lot_id:
            continue
        width, depth = description[20:22]
        street = geography.get(ResourceKey(STREET_DESCRIPTION_TYPE_ID, key.group, street_id))
        street_info = _street(street) if street else None
        region_id, asset = street_info or (0, "")
        region = geography.get(ResourceKey(REGION_DESCRIPTION_TYPE_ID, key.group, region_id), b"")
        candidates = [(k, m) for k, m in manifests[key.instance] if k.group == key.group]
        # Alternate templates without a display name are not additional sites.
        named = [(k, m) for k, m in candidates if m.lot_name_key]
        for manifest_key, record in named or candidates or [(None, None)]:
            template = record.lot_template_id if record else None
            venue = None
            if template:
                for path in reversed(worlds.get(asset.casefold(), [])):
                    venue = _default_venue(path, template, packages)
                    if venue is not None:
                        break
            household_id = record.household_id if record else None
            household = world.households.get(household_id)
            household_name = strings.get(record.household_name_key) if record else None
            lots.append(WorldLot(
                lot_id, name=strings.get(record.lot_name_key) if record else None,
                region_id=region_id or None,
                region_name=strings.get(int.from_bytes(region[4:8], "little")) if len(region) >= 8 else None,
                street_id=street_id or None,
                street_name=strings.get(int.from_bytes(street[4:8], "little")) if street else None,
                world_id=fnv1_32(asset.casefold()) if asset else None,
                pack=record.source.pack if record and record.source else None,
                width=width or None, depth=depth or None,
                venue_id=venue, venue_name=venue_names.get(venue),
                lot_description_id=key.instance, lot_template_id=template,
                manifest_key=manifest_key, starter_household_id=household_id,
                household_name=household_name or (household.name if household else None),
                occupancy=_starter_occupancy(record),
                lot_trait_ids=tuple(initial_traits.get(manifest_key.instance, ())) if manifest_key else None,
            ))
    return LotRegistry(lots)


def _saved_venues(path: Path, zone_ids: set[int]) -> dict[int, int]:
    from ..save.protobuf import iter_fields
    from ..save.source import PERSISTENCE_RESOURCE_TYPE

    if not path.is_file():
        return {}
    try:
        package = DBPF(path)
    except (Sims4SDKError, OSError):
        return {}
    result = {}
    for entry in package.iter_entries(type_id=PERSISTENCE_RESOURCE_TYPE):
        if entry.key.instance not in zone_ids or entry.is_null:
            continue
        try:
            fields = list(iter_fields(package.read_resource(entry)))
            zone = next((int.from_bytes(value, "little") for tag, wire, value in fields
                         if (tag, wire) == (1, 1)), None)
            if zone != entry.key.instance:
                continue
            architectures = [value for tag, wire, value in fields if (tag, wire) == (2, 2)]
            active_index = next((value for tag, wire, value in fields if (tag, wire) == (4, 0)), 0)
            if active_index < len(architectures):
                venue = architecture_venue_id(architectures[active_index])
                if venue is not None:
                    result[zone] = venue
        except (Sims4SDKError, OSError):
            continue
    return result


def overlay_save(base: LotRegistry, save: SaveFile, venue_names: dict[int, str]) -> LotRegistry:
    """Overlay zones on physical sites and retain unmatched sites and zones."""
    by_site = defaultdict(list)
    by_id = defaultdict(list)
    for index, lot in enumerate(base.lots):
        by_site[lot.lot_id, lot.lot_description_id].append(index)
        by_id[lot.lot_id].append(index)
    venues = _saved_venues(save.path, set(save.zones))
    matched = set()
    lots = []
    for zone in save.zones.values():
        if not zone.lot_id:
            continue
        candidates = (by_site[zone.lot_id, zone.lot_description_id] if zone.lot_description_id
                      else by_id[zone.lot_id])
        exact = [index for index in candidates if base.lots[index].lot_template_id == zone.lot_template_id]
        choices = exact or candidates
        if len(choices) == 1:
            index = choices[0]
            matched.add(index)
            lot = base.lots[index]
        else:
            lot = WorldLot(zone.lot_id, lot_description_id=zone.lot_description_id,
                           lot_template_id=zone.lot_template_id)
        neighborhood = save.neighborhoods.get(zone.neighborhood_id)
        household = save.households.get(zone.household_id)
        venue = venues.get(zone.zone_id) or zone.venue_id or lot.venue_id
        occupancy = "occupied" if zone.household_id else "vacant" if zone.household_id == 0 else "unknown"
        lots.append(replace(
            lot, name=zone.name or lot.name,
            region_id=lot.region_id or (neighborhood.region_id if neighborhood else None),
            region_name=lot.region_name or (neighborhood.name if neighborhood else None),
            world_id=zone.world_id or lot.world_id,
            zone_id=zone.zone_id, neighborhood_id=zone.neighborhood_id,
            household_id=zone.household_id or None,
            household_name=household.name if household else None, occupancy=occupancy,
            venue_id=venue, venue_name=venue_names.get(venue),
            lot_trait_ids=tuple(getattr(zone, "lot_trait_ids", ())),
        ))
    # The save does not cover these sites, so their current traits are unknown.
    lots.extend(replace(lot, household_name=None, occupancy="unknown", lot_trait_ids=None)
                for index, lot in enumerate(base.lots) if index not in matched)
    return LotRegistry(lots)
