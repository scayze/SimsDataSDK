"""Coordinated static-data build: catalog + pre-made Sims, with caching."""

from __future__ import annotations

import pickle
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional
from xml.etree import ElementTree

from ..exceptions import Sims4SDKError
from ..export import Serializable, to_dict
from ..installation import Installation, PackageInfo
from .builder import (
    CollectedPackageData,
    add_simdata_statistics,
    cache_key,
    collect_package_data,
    default_cache_dir,
    extract_catalog,
    resolve_relationship_tuning,
    resolve_world_resources,
)
from .models import Catalog
from .diagnostics import ExtractionIssue
from .premades import PremadeBundle, build_premades
from .strings import load_strings
from .worlds import WorldData
from .scenarios import ScenarioData, extract_scenarios

__all__ = [
    "StaticDataError",
    "StaticData",
    "StaticSource",
    "extract_static",
    "resolve_static",
    "build_static",
    "build_catalog",
    "load_static",
]

ProgressCallback = Optional[Callable[[str], None]]
SNAPSHOT_VERSION = 1


@dataclass
class StaticSource(Serializable):
    """Selected package data and strings before catalog and premade resolution.

    Tuning entries retain the selected source resource and can be inspected
    directly. Package collection covers supported formats, not every resource.
    """

    collected: CollectedPackageData
    strings: dict[int, str]
    diagnostics: list[ExtractionIssue] = field(default_factory=list)

    def to_dict(self, *, include_strings: bool = False, **options) -> dict:
        """Export collected records; tuning XML may contain shared references."""
        data = self.collected
        result = {
            "entries": {str(key): {"xml": ElementTree.tostring(entry.element, encoding="unicode"),
                                   "source": data.sources.get(key)}
                        for key, entry in data.entries.items()},
            "tuning_overrides": data.tuning_overrides,
            "simdata_statistics": data.simdata_statistics,
            "world_resources": data.world_resources,
            "siminfo_sources": {str(key): {"path": str(info.path),
                                             "resource_key": str(entry.key)}
                                for key, (info, entry) in data.siminfo_index.items()},
            "diagnostics": [*self.diagnostics, *data.diagnostics],
        }
        if include_strings:
            result["strings"] = self.strings
        return to_dict(result, include_strings=include_strings, **options)


def extract_static(
    installation: Installation, *, packages: Optional[list[PackageInfo]] = None,
    strings_packages: Optional[list[PackageInfo]] = None,
    progress: ProgressCallback = None,
) -> StaticSource:
    """Collect supported source data without building linked catalog views."""
    selected = packages if packages is not None else installation.packages
    string_sources = _string_packages(installation, packages, strings_packages)
    diagnostics: list[ExtractionIssue] = []
    if progress:
        progress(f"loading strings for {installation.locale}")
    strings = load_strings(installation, packages=string_sources, diagnostics=diagnostics)
    if progress:
        progress(f"scanning {len(selected)} packages")
    collected = collect_package_data(selected, progress=progress)
    return StaticSource(collected, strings, diagnostics)


def resolve_static(
    source: StaticSource, *, progress: ProgressCallback = None,
) -> "StaticData":
    """Build linked views without changing the collected source data."""
    collected = source.collected
    entries, sources = collected.entries, collected.sources
    strings = dict(source.strings)
    world = resolve_world_resources(collected)
    if progress:
        progress("resolving catalog")
    catalog = extract_catalog(entries, sources, strings,
                              relationship_tuning=resolve_relationship_tuning(collected))
    catalog.tuning_overrides = deepcopy(collected.tuning_overrides)
    add_simdata_statistics(catalog, collected, strings)
    catalog.finalize()
    catalog.errors.extend(world.errors)
    catalog.diagnostics.extend(deepcopy(source.diagnostics))
    catalog.diagnostics.extend(deepcopy(collected.diagnostics))
    catalog.diagnostics.extend(world.diagnostics)
    if progress:
        progress("resolving pre-made Sims")
    scenario_data = extract_scenarios(entries, sources, strings)
    premades = build_premades(None, catalog, entries, sources, world=world,
                              siminfo_index=collected.siminfo_index, scenario_data=scenario_data)
    return StaticData(catalog=catalog, premades=premades, world=world, scenario_data=scenario_data)


def _string_packages(installation, packages, strings_packages):
    if strings_packages is not None:
        return strings_packages
    if packages is None:
        return installation.string_packages
    selected_packs = {info.pack for info in packages}
    return [info for info in installation.string_packages
            if info.pack in selected_packs or info.pack == "BASE"]


class StaticDataError(Sims4SDKError, ValueError):
    """Raised when a static-data snapshot cannot be saved or loaded."""


@dataclass
class StaticData(Serializable):
    """Everything that can be extracted without reading a save file."""

    catalog: Catalog = field(default_factory=Catalog)
    premades: PremadeBundle = field(default_factory=PremadeBundle)
    #: Original starter-household/lot records; None for older snapshots.
    world: Optional[WorldData] = None
    #: None for snapshots made before scenario extraction was added.
    scenario_data: Optional[ScenarioData] = None

    @property
    def sims(self):
        return self.premades.sims

    @property
    def households(self):
        return self.premades.households

    @property
    def ancestors(self):
        return self.premades.ancestors

    @property
    def lots(self):
        return self.premades.lots

    def sim(self, key: str | int):
        return self.premades.sim(key)

    def ancestor(self, key: str | int):
        return self.premades.ancestor(key)

    def household(self, key: str | int):
        return self.premades.household(key)

    def lot(self, key: str | int):
        return self.premades.lot(key)

    def scenario(self, key: str | int):
        data = getattr(self, "scenario_data", None)
        return data.scenario(key) if data is not None else None

    def find_scenarios(self, query: str = ""):
        data = getattr(self, "scenario_data", None)
        return data.find_scenarios(query) if data is not None else []

    def family_tree(self, key):
        """Build the connected family tree around ``key``; see :meth:`PremadeBundle.family_tree`."""
        return self.premades.family_tree(key)

    def find_sims(self, *args, **kwargs):
        """Filter pre-made Sims; see :meth:`PremadeBundle.find_sims`."""
        return self.premades.find_sims(*args, **kwargs)

    def find_ancestors(self, *args, **kwargs):
        """Filter pre-made ancestors; see :meth:`PremadeBundle.find_ancestors`."""
        return self.premades.find_ancestors(*args, **kwargs)

    def find_households(self, *args, **kwargs):
        """Filter pre-made households; see :meth:`PremadeBundle.find_households`."""
        return self.premades.find_households(*args, **kwargs)

    def find_lots(self, *args, **kwargs):
        """Filter lots; see :meth:`PremadeBundle.find_lots`."""
        return self.premades.find_lots(*args, **kwargs)

    # ------------------------------------------------------------------
    # portable snapshots
    # ------------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        """Write a portable snapshot (catalog + pre-mades) and return its path.

        The snapshot can be loaded later with :meth:`load` on a machine that
        does not have The Sims 4 installed, then used to read saves and Tray
        files against a fixed catalog.
        """
        target = Path(path)
        try:
            if target.parent:
                target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                pickle.dump({"version": SNAPSHOT_VERSION, "data": self}, handle,
                            protocol=pickle.HIGHEST_PROTOCOL)
        except OSError as exc:
            raise StaticDataError(f"cannot write static data to {target}: {exc}") from exc
        return target

    @classmethod
    def load(cls, path: str | Path) -> "StaticData":
        """Load a snapshot written by :meth:`save`."""
        target = Path(path)
        try:
            with target.open("rb") as handle:
                value = pickle.load(handle)
        except OSError as exc:
            raise StaticDataError(
                f"cannot read static data from {target}: {exc}"
            ) from exc
        except Exception as exc:
            raise StaticDataError(
                f"{target} is not a valid static-data snapshot: {exc}"
            ) from exc
        if not isinstance(value, dict) or value.get("version") != SNAPSHOT_VERSION:
            raise StaticDataError(f"{target} has an unsupported static-data snapshot version")
        if not isinstance(value.get("data"), cls):
            raise StaticDataError(f"{target} does not contain StaticData")
        return value["data"]

    def summary(self) -> str:
        return (
            f"{self.catalog.summary()} | premade sims={len(self.premades.sims)}, "
            f"households={len(self.premades.households)}, "
            f"ancestors={len(self.premades.ancestors)}, "
            f"lots={len(self.premades.lots)}"
        )


def build_static(
    installation: Installation,
    *,
    packages: Optional[list[PackageInfo]] = None,
    strings_packages: Optional[list[PackageInfo]] = None,
    use_cache: bool = True,
    refresh: bool = False,
    cache_dir: str | Path | None = None,
    progress: ProgressCallback = None,
) -> StaticData:
    """Build (or load) the static catalog and pre-made Sim bundle."""
    selected = packages if packages is not None else installation.packages
    strings_packages = _string_packages(installation, packages, strings_packages)
    key = cache_key(installation, selected, installation.locale, strings_packages=strings_packages)
    directory = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    cache_file = directory / f"static-{key}.pkl"

    if use_cache and not refresh and cache_file.exists():
        try:
            with cache_file.open("rb") as handle:
                cached = pickle.load(handle)
            if isinstance(cached, StaticData):
                if progress:
                    progress(f"loaded cached static data {cache_file.name}")
                return cached
        except Exception:
            pass

    source = extract_static(installation, packages=selected, strings_packages=strings_packages,
                            progress=progress)
    data = resolve_static(source, progress=progress)

    if use_cache:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with cache_file.open("wb") as handle:
                pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
            if progress:
                progress(f"wrote cache {cache_file.name}")
        except OSError:
            pass

    return data


def build_catalog(
    installation: Installation,
    *,
    packages: Optional[list[PackageInfo]] = None,
    use_cache: bool = True,
    refresh: bool = False,
    cache_dir: str | Path | None = None,
    progress: ProgressCallback = None,
) -> Catalog:
    """Convenience wrapper returning only the catalog."""
    return build_static(
        installation,
        packages=packages,
        use_cache=use_cache,
        refresh=refresh,
        cache_dir=cache_dir,
        progress=progress,
    ).catalog


def load_static(
    installation: Installation,
    *,
    packages: Optional[list[PackageInfo]] = None,
    strings_packages: Optional[list[PackageInfo]] = None,
    cache_dir: str | Path | None = None,
) -> Optional[StaticData]:
    """Load cached static data without rebuilding, or return ``None``."""
    selected = packages if packages is not None else installation.packages
    strings_packages = _string_packages(installation, packages, strings_packages)
    key = cache_key(installation, selected, installation.locale, strings_packages=strings_packages)
    directory = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    cache_file = directory / f"static-{key}.pkl"
    if not cache_file.exists():
        return None
    try:
        with cache_file.open("rb") as handle:
            cached = pickle.load(handle)
        return cached if isinstance(cached, StaticData) else None
    except Exception:
        return None
