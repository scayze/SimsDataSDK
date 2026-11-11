"""Coordinated static-data build: catalog + pre-made Sims, with caching."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..exceptions import Sims4SDKError
from ..export import Serializable
from ..installation import Installation, PackageInfo
from .builder import (
    cache_key,
    collect_package_data,
    default_cache_dir,
    extract_catalog,
)
from .models import Catalog
from .premades import PremadeBundle, build_premades
from .strings import load_strings

__all__ = [
    "StaticDataError",
    "StaticData",
    "build_static",
    "build_catalog",
    "load_static",
]

ProgressCallback = Optional[Callable[[str], None]]


class StaticDataError(Sims4SDKError, ValueError):
    """Raised when a static-data snapshot cannot be saved or loaded."""


@dataclass
class StaticData(Serializable):
    """Everything that can be extracted without reading a save file."""

    catalog: Catalog = field(default_factory=Catalog)
    premades: PremadeBundle = field(default_factory=PremadeBundle)

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

    def household(self, key: str | int):
        return self.premades.household(key)

    def lot(self, key: str | int):
        return self.premades.lot(key)

    def find_sims(self, *args, **kwargs):
        """Filter pre-made Sims; see :meth:`PremadeBundle.find_sims`."""
        return self.premades.find_sims(*args, **kwargs)

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
                pickle.dump(self, handle, protocol=pickle.HIGHEST_PROTOCOL)
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
        if not isinstance(value, cls):
            raise StaticDataError(f"{target} does not contain StaticData")
        return value

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
    if strings_packages is None:
        if packages is None:
            strings_packages = installation.string_packages
        else:
            selected_packs = {info.pack for info in selected}
            strings_packages = [
                info
                for info in installation.string_packages
                if info.pack in selected_packs or info.pack == "BASE"
            ]
    key = cache_key(installation, selected, installation.locale)
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

    if progress:
        progress(f"loading strings for {installation.locale}")
    strings = load_strings(installation, packages=strings_packages)
    if progress:
        progress(f"loaded {len(strings):,} strings")

    if progress:
        progress(f"scanning {len(selected)} packages")
    collected = collect_package_data(selected, progress=progress)
    entries, sources, world = collected.entries, collected.sources, collected.world
    if progress:
        progress(
            f"extracted {len(entries):,} tuning entries, "
            f"{len(world.households):,} household resources, "
            f"{len(world.lots):,} lot records, "
            f"{len(collected.relationship_tuning.defaults):,} relationship defaults, "
            f"{len(collected.relationship_tuning.pairs):,} premade relationships"
        )

    if progress:
        progress("extracting catalog")
    catalog = extract_catalog(
        entries,
        sources,
        strings,
        relationship_tuning=collected.relationship_tuning,
    )
    catalog.errors.extend(world.errors)

    if progress:
        progress("extracting pre-made Sims")
    premades = build_premades(
        installation,
        catalog,
        entries,
        sources,
        world=world,
        siminfo_index=collected.siminfo_index,
    )

    data = StaticData(catalog=catalog, premades=premades)

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
    cache_dir: str | Path | None = None,
) -> Optional[StaticData]:
    """Load cached static data without rebuilding, or return ``None``."""
    selected = packages if packages is not None else installation.packages
    key = cache_key(installation, selected, installation.locale)
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
