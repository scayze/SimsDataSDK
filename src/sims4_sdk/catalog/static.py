"""Coordinated static-data build: catalog + pre-made Sims, with caching."""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ..installation import Installation, PackageInfo
from .builder import (
    cache_key,
    collect_entries,
    default_cache_dir,
    extract_catalog,
)
from .models import Catalog
from .premades import PremadeBundle, build_premades
from .strings import load_strings

__all__ = ["StaticData", "build_static", "build_catalog", "load_static"]

ProgressCallback = Optional[Callable[[str], None]]


@dataclass
class StaticData:
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

    def sim(self, key: str | int):
        return self.premades.sim(key)

    def household(self, key: str | int):
        return self.premades.household(key)

    def summary(self) -> str:
        return (
            f"{self.catalog.summary()} | premade sims={len(self.premades.sims)}, "
            f"households={len(self.premades.households)}, "
            f"ancestors={len(self.premades.ancestors)}"
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
        progress(f"scanning {len(selected)} tuning packages")
    entries, sources = collect_entries(selected, progress=progress)
    if progress:
        progress(f"extracted {len(entries):,} tuning entries")

    if progress:
        progress("extracting catalog")
    catalog = extract_catalog(entries, sources, strings)

    if progress:
        progress("extracting pre-made Sims")
    premades = build_premades(installation, catalog, entries, sources)

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
