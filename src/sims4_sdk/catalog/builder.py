"""Build the save-independent static catalog from game/DLC/mod packages."""

from __future__ import annotations

import hashlib
import os
import pickle
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Optional

from ..core import (
    COMBINED_TUNING_TYPE_ID,
    DBPF,
    LOT_MANIFEST_TYPE_ID,
    PREMADE_HOUSEHOLD_TYPE_ID,
    TUNING_TYPE_ID,
    CombinedTuning,
    ResourceEntry,
    TuningElement,
)
from ..installation import Installation, PackageInfo, SIMINFO_TYPE_ID
from .models import (
    Aspiration,
    AspirationCategory,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    Milestone,
    Preference,
    RelationshipBit,
    Trait,
    TuningSource,
)
from .strings import load_strings
from .diagnostics import ExtractionIssue
from .values import TuningView
from .relationships import (
    FRIENDSHIP_TRACK_ID,
    RELATIONSHIP_MODULES,
    ROMANCE_TRACK_ID,
    RelationshipTuningData,
    extract_relationship_tuning,
    has_interval_data,
)
from .worlds import WorldData

__all__ = [
    "build_catalog",
    "collect_entries",
    "collect_package_data",
    "extract_catalog",
    "default_cache_dir",
    "cache_key",
]

ProgressCallback = Optional[Callable[[str], None]]

CACHE_VERSION = "step2-13"

_LEVEL_PATTERN = re.compile(r"(?:^|_)Level(\d+)(?:$|_)", re.IGNORECASE)
_MODEL_CLASSES = frozenset(
    {
        "Trait",
        "Preference",
        "Aspiration",
        "AspirationTrack",
        "AspirationCategory",
        "Career",
        "TunableCareerTrack",
        "CareerLevel",
        "DevelopmentalMilestone",
        "RelationshipBit",
    }
)
#: Resource types the catalog build reads; everything else is skipped without
#: being materialised.
_SCANNED_TYPES = frozenset(
    {
        COMBINED_TUNING_TYPE_ID,
        TUNING_TYPE_ID,
        PREMADE_HOUSEHOLD_TYPE_ID,
        LOT_MANIFEST_TYPE_ID,
        SIMINFO_TYPE_ID,
    }
)

_DAY_NAMES = ("SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY")


def default_cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "sims4-sdk" / "cache"


def cache_key(
    installation: Installation,
    packages: Iterable[PackageInfo],
    locale: str,
    *,
    strings_packages: Optional[Iterable[PackageInfo]] = None,
) -> str:
    digest = hashlib.sha256()
    digest.update(CACHE_VERSION.encode("utf-8"))
    digest.update(str(installation.install_dir).encode("utf-8"))
    digest.update(locale.encode("utf-8"))
    digest.update(str(installation.include_mods).encode("utf-8"))
    for label, sources in (("packages", packages), ("strings", strings_packages or ())):
        digest.update(label.encode("utf-8"))
        for info in sources:
            try:
                stat = info.path.stat()
                stamp = f"{stat.st_mtime_ns}:{stat.st_size}"
            except OSError:
                stamp = "missing"
            digest.update(f"{info.path}|{info.pack}|{info.is_mod}|{stamp}".encode("utf-8"))
    return digest.hexdigest()[:32]


def build_catalog(
    installation: Installation,
    packages: Optional[list[PackageInfo]] = None,
    *,
    use_cache: bool = True,
    cache_dir: str | Path | None = None,
    progress: ProgressCallback = None,
) -> Catalog:
    """Build (or load) the static catalog.

    Parameters
    ----------
    packages:
        Optional subset of packages to scan.  Strings are still loaded from the
        normal string packages so display names resolve.
    use_cache:
        Load/save a pickled catalog keyed by package mtimes and sizes.
    """
    selected = packages if packages is not None else installation.packages
    strings_packages = installation.string_packages
    key = cache_key(installation, selected, installation.locale, strings_packages=strings_packages)
    directory = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    cache_file = directory / f"catalog-{key}.pkl"

    if use_cache and cache_file.exists():
        try:
            with cache_file.open("rb") as handle:
                cached = pickle.load(handle)
            if isinstance(cached, Catalog):
                if progress:
                    progress(f"loaded cached catalog {cache_file.name}")
                return cached
        except Exception:
            # Corrupt cache: fall through and rebuild.
            pass

    if progress:
        progress(f"loading strings for {installation.locale}")
    diagnostics: list[ExtractionIssue] = []
    strings = load_strings(installation, packages=strings_packages, diagnostics=diagnostics)
    if progress:
        progress(f"loaded {len(strings):,} strings")

    if progress:
        progress(f"scanning {len(selected)} tuning packages")
    collected = collect_package_data(selected, progress=progress, include_world=False)
    entries, sources = collected.entries, collected.sources
    if progress:
        progress(f"extracted {len(entries):,} tuning entries")

    catalog = extract_catalog(
        entries, sources, strings, relationship_tuning=collected.relationship_tuning
    )
    catalog.diagnostics.extend(diagnostics)
    catalog.diagnostics.extend(collected.diagnostics)

    if progress:
        progress("linking catalog entries")
    catalog.finalize()

    if use_cache:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with cache_file.open("wb") as handle:
                pickle.dump(catalog, handle, protocol=pickle.HIGHEST_PROTOCOL)
            if progress:
                progress(f"wrote cache {cache_file.name}")
        except OSError:
            pass

    return catalog


# ----------------------------------------------------------------------
# tuning collection
# ----------------------------------------------------------------------
@dataclass
class CollectedPackageData:
    """Tuning plus world resources collected from one package pass."""

    entries: dict[int, TuningElement] = field(default_factory=dict)
    sources: dict[int, TuningSource] = field(default_factory=dict)
    world: WorldData = field(default_factory=WorldData)
    relationship_modules: dict[str, CombinedTuning] = field(
        default_factory=dict, repr=False
    )
    relationship_track_sources: dict[int, TuningElement] = field(
        default_factory=dict, repr=False
    )
    relationship_tuning: RelationshipTuningData = field(
        default_factory=RelationshipTuningData
    )
    #: SimInfo instance -> (package, index entry), collected in the same pass so
    #: pre-made Sim extraction does not have to re-open every package.
    siminfo_index: dict[int, tuple[PackageInfo, ResourceEntry]] = field(
        default_factory=dict, repr=False
    )
    diagnostics: list[ExtractionIssue] = field(default_factory=list)


def collect_package_data(
    packages: Iterable[PackageInfo],
    *,
    progress: ProgressCallback = None,
    include_world: bool = True,
    include_relationships: bool = True,
    include_siminfo: bool = True,
) -> CollectedPackageData:
    """Open every package once and collect tuning and world resources."""
    data = CollectedPackageData()
    # Several packs ship the same Combined Tuning blob in both their
    # ``SimulationPreload`` and ``SimulationDeltaBuild0`` packages.  Parsing
    # the DATA tables is the most expensive part of a cold build, so reuse the
    # parsed object when the raw bytes are identical.
    combined_cache: dict[bytes, CombinedTuning] = {}

    for info in packages:
        if progress:
            progress(f"  {info.label}: {info.path.name}")
        try:
            package = DBPF(info.path)
        except Exception as exc:
            data.diagnostics.append(ExtractionIssue.from_exception(
                "package_open", exc, package_path=str(info.path)
            ))
            continue

        source = TuningSource(
            package=str(info.path.name),
            pack=info.pack,
            is_mod=info.is_mod,
            path=str(info.path),
        )

        combined_blobs: list[tuple[bytes, TuningSource]] = []
        # One pass over the index: the entry lists are millions of rows long, so
        # filtering them once saves a full scan per resource type.
        for entry in package.iter_entries_for_types(_SCANNED_TYPES):
            type_id = entry.key.type_id
            entry_source = replace(source, resource_key=entry.key)
            if type_id == COMBINED_TUNING_TYPE_ID:
                try:
                    combined_blobs.append((DBPF.read_entry(package.path, entry), entry_source))
                except Exception as exc:
                    data.diagnostics.append(ExtractionIssue.from_exception(
                        "resource_read", exc, package_path=str(info.path), resource_key=entry.key
                    ))
                    continue
            elif type_id == TUNING_TYPE_ID:
                # Individual tuning XML resources (common in mods).
                try:
                    raw = DBPF.read_entry(package.path, entry)
                    text = raw.decode("utf-8-sig", errors="replace")
                    try:
                        combined = CombinedTuning.from_xml(text)
                    except Exception:
                        # Some mods ship several top-level <I> elements.
                        combined = CombinedTuning.from_xml(f"<root>{text}</root>")
                except Exception as exc:
                    data.diagnostics.append(ExtractionIssue.from_exception(
                        "tuning_read", exc, package_path=str(info.path), resource_key=entry.key
                    ))
                    continue
                for tuning in combined:
                    data.entries[tuning.instance_id] = tuning
                    data.sources[tuning.instance_id] = entry_source
            elif type_id == PREMADE_HOUSEHOLD_TYPE_ID:
                if include_world:
                    try:
                        raw = DBPF.read_entry(package.path, entry)
                    except Exception as exc:
                        data.diagnostics.append(ExtractionIssue.from_exception(
                            "resource_read", exc, package_path=str(info.path), resource_key=entry.key
                        ))
                    else:
                        data.world.add_household(entry.key.instance, raw, entry_source)
            elif type_id == LOT_MANIFEST_TYPE_ID:
                if include_world:
                    try:
                        raw = DBPF.read_entry(package.path, entry)
                    except Exception as exc:
                        data.diagnostics.append(ExtractionIssue.from_exception(
                            "resource_read", exc, package_path=str(info.path), resource_key=entry.key
                        ))
                    else:
                        data.world.add_lot(entry.key.instance, raw, entry_source)
            elif type_id == SIMINFO_TYPE_ID:
                if include_siminfo:
                    data.siminfo_index[entry.key.instance] = (info, entry)

        # Combined tuning (the main source for retail packages) is applied after
        # the per-entry XML so that it wins within a package.
        for raw, entry_source in combined_blobs:
            content_key = hashlib.blake2b(raw, digest_size=16).digest()
            combined = combined_cache.get(content_key)
            if combined is None:
                try:
                    combined = CombinedTuning.parse(raw)
                except Exception as exc:
                    data.diagnostics.append(ExtractionIssue.from_exception(
                        "combined_tuning", exc, package_path=str(info.path),
                        resource_key=entry_source.resource_key,
                    ))
                    continue
                combined_cache[content_key] = combined
            for tuning in combined:
                data.entries[tuning.instance_id] = tuning
                data.sources[tuning.instance_id] = entry_source
            if include_relationships:
                for module_name in RELATIONSHIP_MODULES:
                    if module_name in combined.modules:
                        data.relationship_modules[module_name] = combined
                for track_id in (FRIENDSHIP_TRACK_ID, ROMANCE_TRACK_ID):
                    element = combined.find_by_instance_id(track_id)
                    if element is not None and has_interval_data(element):
                        data.relationship_track_sources[track_id] = element

    if include_world:
        data.world.finalize()
    if include_relationships and data.relationship_modules:
        data.relationship_tuning = extract_relationship_tuning(
            data.relationship_modules,
            data.entries,
            track_sources=data.relationship_track_sources,
        )
    return data


def collect_entries(
    packages: Iterable[PackageInfo],
    *,
    progress: ProgressCallback = None,
) -> tuple[dict[int, TuningElement], dict[int, TuningSource]]:
    """Collect only tuning entries (kept for backwards compatibility)."""
    data = collect_package_data(
        packages,
        progress=progress,
        include_world=False,
        include_relationships=False,
    )
    return data.entries, data.sources


# ----------------------------------------------------------------------
# model extraction
# ----------------------------------------------------------------------
def extract_catalog(
    entries: dict[int, TuningElement],
    sources: dict[int, TuningSource],
    strings: dict[int, str],
    *,
    relationship_tuning: Optional[RelationshipTuningData] = None,
) -> Catalog:
    catalog = Catalog(strings=strings)
    _build_models(catalog, entries, sources, strings)
    if relationship_tuning is not None:
        catalog.relationship_defaults = relationship_tuning.defaults
        catalog.premade_relationships = relationship_tuning.pairs
        catalog.relationship_track_ranges = relationship_tuning.track_ranges
        catalog.steady_bit_id = relationship_tuning.steady_bit_id
        catalog.engagement_bit_id = relationship_tuning.engagement_bit_id
        catalog.marriage_bit_id = relationship_tuning.marriage_bit_id
        catalog.family_trope_ids = relationship_tuning.family_trope_ids
        catalog.romance_trope_ids = relationship_tuning.romance_trope_ids
    catalog.finalize()
    return catalog


def _build_models(
    catalog: Catalog,
    entries: dict[int, TuningElement],
    sources: dict[int, TuningSource],
    strings: dict[int, str],
) -> None:
    for instance_id, entry in entries.items():
        source = sources.get(instance_id)
        cls = entry.cls
        catalog.tuning_names[instance_id] = entry.name
        catalog.tuning_classes[instance_id] = cls
        if cls not in _MODEL_CLASSES:
            continue
        try:
            view = TuningView(entry, strings)
            if cls == "Trait":
                catalog.traits[instance_id] = _build_trait(entry, view, source)
            elif cls == "Preference":
                catalog.preferences[instance_id] = _build_preference(entry, view, source)
            elif cls == "Aspiration":
                catalog.aspirations[instance_id] = _build_aspiration(entry, view, source)
            elif cls == "AspirationTrack":
                catalog.aspiration_tracks[instance_id] = _build_aspiration_track(
                    entry, view, source
                )
            elif cls == "AspirationCategory":
                catalog.aspiration_categories[instance_id] = _build_aspiration_category(
                    entry, view, source
                )
            elif cls == "Career":
                catalog.careers[instance_id] = _build_career(entry, view, source)
            elif cls == "TunableCareerTrack":
                catalog.career_tracks[instance_id] = _build_career_track(
                    entry, view, source
                )
            elif cls == "CareerLevel":
                catalog.career_levels[instance_id] = _build_career_level(
                    entry, view, source
                )
            elif cls == "DevelopmentalMilestone":
                catalog.milestones[instance_id] = _build_milestone(entry, view, source)
            elif cls == "RelationshipBit":
                catalog.relationship_bits[instance_id] = _build_relationship_bit(
                    entry, view, source
                )
        except Exception as exc:  # keep one bad definition from aborting the scan
            catalog.errors.append(f"{entry.name} ({entry.cls}): {exc}")
            catalog.diagnostics.append(ExtractionIssue.from_exception(
                "catalog_model", exc, package_path=source.path if source else None,
                resource_key=source.resource_key if source else None, tuning_id=instance_id,
            ))


def _build_trait(entry: TuningElement, view: TuningView, source) -> Trait:
    trait_type = view.enum("trait_type") or entry.tuning_type
    conflicting = view.list_numbers("conflicting_traits")
    if not conflicting:
        conflicting = view.list_numbers("opposite_traits")
    return Trait(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("display_name")
        or view.text("display_name_gender_neutral")
        or entry.name,
        description=view.text("trait_description"),
        trait_type=trait_type,
        ages=view.list_enums("ages"),
        species=view.list_enums("species"),
        occults=view.list_enums("occults"),
        ui_category=view.variant("ui_category")[0],
        is_hidden=trait_type.upper() == "HIDDEN",
        icon=view.text("icon"),
        conflicting_trait_ids=conflicting,
        source=source,
    )


def _build_preference(entry: TuningElement, view: TuningView, source) -> Preference:
    return Preference(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("display_name")
        or view.text("display_name_gender_neutral")
        or entry.name,
        description=view.text("trait_description"),
        preference_type=view.enum("trait_type") or "PREFERENCE",
        item=view.text("preference_item") or view.raw_text("preference_item"),
        ages=view.list_enums("ages"),
        species=view.list_enums("species"),
        conflicting_trait_ids=view.list_numbers("conflicting_traits"),
        source=source,
    )


def _build_aspiration(entry: TuningElement, view: TuningView, source) -> Aspiration:
    return Aspiration(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("display_name") or entry.name,
        description=view.text("descriptive_text") or view.text("description"),
        valid_ages=view.list_enums("aspiration_valid_age_type"),
        objective_ids=view.list_numbers("objectives"),
        icon=view.text("icon"),
        source=source,
    )


def _build_aspiration_track(
    entry: TuningElement, view: TuningView, source
) -> AspirationTrack:
    return AspirationTrack(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("display_text") or entry.name,
        description=view.text("description_text"),
        category_id=view.number("category"),
        aspiration_ids=_aspiration_ids(view),
        primary_trait_id=view.number("primary_trait"),
        reward_id=view.number("reward"),
        icon=view.text("icon"),
        source=source,
    )


def _aspiration_ids(view: TuningView) -> list[int]:
    element = view.resolved_child("aspirations")
    if element is None:
        return []
    ids: list[int] = []
    for item in element:
        resolved = view.resolve(item)
        if resolved is None:
            continue
        if resolved.tag == "U":
            value_element = next(
                (child for child in resolved if child.get("n") == "value"), None
            )
            number = view.number_of(value_element)
        else:
            number = view.number_of(resolved)
        if number is not None:
            ids.append(number)
    return ids


def _build_aspiration_category(
    entry: TuningElement, view: TuningView, source
) -> AspirationCategory:
    return AspirationCategory(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("display_text") or entry.name,
        sort_order=view.number("ui_sort_order"),
        source=source,
    )


def _build_career(entry: TuningElement, view: TuningView, source) -> Career:
    return Career(
        id=entry.instance_id,
        name=entry.name,
        start_track_id=view.number("start_track"),
        category=view.raw_text("career_category"),
        source=source,
    )


def _build_career_track(
    entry: TuningElement, view: TuningView, source
) -> CareerTrack:
    return CareerTrack(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("career_name") or entry.name,
        description=view.text("career_description"),
        level_ids=view.list_numbers("career_levels"),
        icon=view.text("icon"),
        source=source,
    )


def _build_career_level(
    entry: TuningElement, view: TuningView, source
) -> CareerLevel:
    pay_type, pay_payload = view.variant("pay_type")
    pay_per_hour = view.number_of(pay_payload)
    work_days, work_start, work_duration = _work_schedule(view)
    level = _level_number(entry.name)
    return CareerLevel(
        id=entry.instance_id,
        name=entry.name,
        title=view.text("title") or entry.name,
        description=view.text("title_description"),
        level=level,
        pay_per_hour=pay_per_hour,
        pay_type=pay_type,
        aspiration_id=view.number("aspiration"),
        promotion_reward_id=view.number("promotion_reward"),
        work_days=work_days,
        work_start_time=work_start,
        work_duration=work_duration,
        source=source,
    )


def _level_number(name: str) -> Optional[int]:
    match = _LEVEL_PATTERN.search(name)
    return int(match.group(1)) if match else None


def _work_schedule(view: TuningView) -> tuple[list[str], Optional[int], Optional[int]]:
    element = view.resolved_child("work_schedule")
    if element is None:
        return [], None, None
    entries = element.find("L") if element.tag == "U" else element
    if entries is None:
        return [], None, None
    first = next(iter(entries), None)
    if first is None:
        return [], None, None
    first = view.resolve(first)
    if first is None:
        return [], None, None

    days: list[str] = []
    day_container = next((c for c in first if c.get("n") == "days_available"), None)
    day_container = view.resolve(day_container)
    if day_container is not None:
        for child in day_container:
            name = (child.get("n") or "").split(" ", 1)[-1]
            if name not in _DAY_NAMES:
                continue
            if view.flag_of(child):
                days.append(name)

    start = next((c for c in first if c.get("n") == "start_time"), None)
    duration = next((c for c in first if c.get("n") == "duration"), None)
    return days, view.number_of(start), view.number_of(duration)


def _build_milestone(entry: TuningElement, view: TuningView, source) -> Milestone:
    primary_type, _ = view.variant("is_primary_milestone")
    return Milestone(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("name") or entry.name,
        description=view.text("unlocked_text") or view.text("unlocked_text_no_context"),
        category=view.raw_text("category") or view.text("category"),
        ages=view.list_enums("ages"),
        repeatable=view.flag("repeatable"),
        is_primary=primary_type not in (None, "False", "false"),
        goal_id=view.number("goal"),
        icon=view.text("icon"),
        unlocked_text=view.text("unlocked_text"),
        source=source,
    )


def _build_relationship_bit(
    entry: TuningElement, view: TuningView, source
) -> RelationshipBit:
    return RelationshipBit(
        id=entry.instance_id,
        name=entry.name,
        display_name=view.text("display_name") or entry.name,
        description=view.text("bit_description"),
        depth=view.number("depth"),
        visible=view.flag("visible", default=True),
        icon=view.text("icon"),
        triggered_track_id=view.number("triggered_track"),
        source=source,
    )
