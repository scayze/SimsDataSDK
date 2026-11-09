"""High-level SDK entry point.

``Sims4Workspace`` discovers the game and user directories, then exposes the
save-independent static data (catalog + pre-made Sims).  Save and Tray readers
are added in Step 3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from .catalog import Catalog, PremadeAncestor, PremadeHousehold, PremadeSim, StaticData, build_static
from .installation import Installation

__all__ = ["Sims4Workspace"]

ProgressCallback = Optional[Callable[[str], None]]


class Sims4Workspace:
    """A convenient facade over an installation and its static data."""

    def __init__(
        self,
        install_dir: str | Path | None = None,
        user_dir: str | Path | None = None,
        *,
        locale: str = "ENG_US",
        include_mods: bool = True,
        cache_dir: str | Path | None = None,
    ):
        self.installation = Installation(
            install_dir=install_dir,
            user_dir=user_dir,
            locale=locale,
            include_mods=include_mods,
        )
        self.cache_dir = cache_dir
        self._static: Optional[StaticData] = None

    # ------------------------------------------------------------------
    # static data
    # ------------------------------------------------------------------
    def static_data(
        self,
        *,
        use_cache: bool = True,
        refresh: bool = False,
        progress: ProgressCallback = None,
    ) -> StaticData:
        if refresh:
            self._static = None
        if self._static is None or not use_cache:
            self._static = build_static(
                self.installation,
                use_cache=use_cache,
                refresh=refresh,
                cache_dir=self.cache_dir,
                progress=progress,
            )
        return self._static

    @property
    def catalog(self) -> Catalog:
        return self.static_data().catalog

    def premade_sims(self, *, refresh: bool = False) -> list[PremadeSim]:
        return self.static_data(refresh=refresh).premades.sims

    def premade_households(self, *, refresh: bool = False) -> list[PremadeHousehold]:
        return self.static_data(refresh=refresh).premades.households

    def ancestors(self, *, refresh: bool = False) -> list[PremadeAncestor]:
        return self.static_data(refresh=refresh).premades.ancestors

    def find_sim(self, key: str | int) -> Optional[PremadeSim]:
        return self.static_data().sim(key)

    def find_household(self, key: str | int) -> Optional[PremadeHousehold]:
        return self.static_data().household(key)

    # ------------------------------------------------------------------
    # misc
    # ------------------------------------------------------------------
    def refresh(self) -> StaticData:
        return self.static_data(refresh=True)

    def __repr__(self) -> str:
        return f"Sims4Workspace({self.installation!r})"
