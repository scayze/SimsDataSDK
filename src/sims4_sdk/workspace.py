"""High-level SDK entry point.

``Sims4Workspace`` discovers the game and user directories, then exposes the
save-independent static data (catalog, pre-made Sims/households/lots), the save
reader, the Tray reader, and Wiki validation.

A workspace can also run without a game installation by loading a portable
snapshot produced with :meth:`StaticData.save`::

    from sims4_sdk import Sims4Workspace

    ws = Sims4Workspace.from_static("sims4-static.pkl", user_dir="C:/.../The Sims 4")
    save = ws.read_save(ws.latest_save_path())
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
import re
from typing import Callable, Iterable, Optional

from .catalog import (
    Catalog,
    FamilyTree,
    PremadeAncestor,
    PremadeHousehold,
    PremadeLot,
    PremadeSim,
    StaticData,
    StaticDataError,
    build_static,
)
from .installation import Installation
from .paths import find_user_dir, iter_pack_root_folders
from .exceptions import Sims4SDKError
from .export import Serializable
from .save import SaveFile, TrayLibrary, read_save, read_tray_library

__all__ = ["Sims4Workspace"]

ProgressCallback = Optional[Callable[[str], None]]


class PackStatusError(Sims4SDKError, ValueError):
    """Invalid pack ID or ownership filter."""


@dataclass(frozen=True)
class PackStatus(Serializable):
    pack_id: str
    owned: Optional[bool]
    installed: Optional[bool]

    def to_dict(self, **options) -> dict:
        return {"pack_id": self.pack_id, "owned": self.owned, "installed": self.installed}


def _pack_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"BASE|(?:EP|GP|SP|FP)\d+", value.upper()):
        raise PackStatusError(f"invalid pack ID: {value!r}")
    return value.upper()


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
        static: StaticData | str | Path | None = None,
        owned_packs: Iterable[str] | None = None,
    ):
        self.locale = locale
        self.include_mods = include_mods
        self.cache_dir = cache_dir
        if isinstance(owned_packs, str):
            raise PackStatusError("owned_packs must be an iterable of pack IDs, not a string")
        self.owned_packs = None if owned_packs is None else frozenset(_pack_id(p) for p in owned_packs)
        self._static: Optional[StaticData] = None
        self._static_provided = static is not None
        self.installation: Optional[Installation] = None

        if static is not None:
            self._static = (
                StaticData.load(static)
                if isinstance(static, (str, Path))
                else static
            )

        try:
            self.installation = Installation(
                install_dir=install_dir,
                user_dir=user_dir,
                locale=locale,
                include_mods=include_mods,
            )
        except FileNotFoundError:
            # Offline mode is only valid with a pre-built snapshot.
            if static is None:
                raise

        if user_dir is not None:
            self.user_dir = Path(user_dir)
        elif self.installation is not None:
            self.user_dir = self.installation.user_dir
        else:
            self.user_dir = find_user_dir()

    # ------------------------------------------------------------------
    # constructors
    # ------------------------------------------------------------------
    @classmethod
    def from_static(
        cls,
        static: StaticData | str | Path,
        *,
        user_dir: str | Path | None = None,
        install_dir: str | Path | None = None,
        locale: str = "ENG_US",
        include_mods: bool = True,
        cache_dir: str | Path | None = None,
        owned_packs: Iterable[str] | None = None,
    ) -> "Sims4Workspace":
        """Open a workspace backed by a pre-built static-data snapshot.

        The game installation is optional; ``user_dir`` is only needed for
        :meth:`save_files`, :meth:`read_saves`, and :meth:`tray_library`.
        """
        return cls(
            install_dir=install_dir,
            user_dir=user_dir,
            locale=locale,
            include_mods=include_mods,
            cache_dir=cache_dir,
            static=static,
            owned_packs=owned_packs,
        )

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
        if refresh or self._static is None or (not use_cache and not self._static_provided):
            if self.installation is None:
                raise StaticDataError(
                    "no game installation is available; open the workspace with "
                    "Sims4Workspace(static=...) or Sims4Workspace.from_static(...)"
                )
            self._static = build_static(
                self.installation,
                use_cache=use_cache,
                refresh=refresh,
                cache_dir=self.cache_dir,
                progress=progress,
            )
            self._static_provided = False
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

    def lots(self, *, refresh: bool = False) -> list[PremadeLot]:
        return self.static_data(refresh=refresh).premades.lots

    def find_sim(self, key: str | int) -> Optional[PremadeSim]:
        return self.static_data().sim(key)

    def scenario(self, key: str | int):
        """Look up a scenario by ID, name, or name fragment."""
        return self.static_data().scenario(key)

    def find_scenario(self, key: str | int):
        """Look up a scenario by ID, name, or name fragment."""
        return self.scenario(key)

    def find_scenarios(self, query: str = ""):
        """Find scenarios by case-insensitive name fragment."""
        return self.static_data().find_scenarios(query)

    def find_ancestor(self, key: str | int) -> Optional[PremadeAncestor]:
        return self.static_data().ancestor(key)

    def find_household(self, key: str | int) -> Optional[PremadeHousehold]:
        return self.static_data().household(key)

    def find_lot(self, key: str | int) -> Optional[PremadeLot]:
        return self.static_data().lot(key)

    def family_tree(
        self, key: str | int | PremadeSim | PremadeAncestor
    ) -> Optional[FamilyTree]:
        """Build the connected family tree around a pre-made Sim or ancestor."""
        return self.static_data().family_tree(key)

    def pack_status(self, pack_id: str) -> PackStatus:
        """Return supplied ownership and the estimated local installation state."""
        pack = _pack_id(pack_id)
        owned = True if pack == "BASE" else (None if self.owned_packs is None else pack in self.owned_packs)
        installed = None
        if self.installation is not None:
            installed = pack == "BASE" or pack in {p.name.upper() for p in iter_pack_root_folders(self.installation.install_dir)}
        return PackStatus(pack, owned, installed)

    def sim_ownership(self, sim: PremadeSim) -> str:
        """Return owned, unowned, or unknown for a premade Sim."""
        pack = getattr(sim, "pack_id", None)
        if not isinstance(pack, str) or not re.fullmatch(r"BASE|(?:EP|GP|SP|FP)\d+", pack.upper()):
            return "unknown"
        status = self.pack_status(pack).owned
        return "unknown" if status is None else "owned" if status else "unowned"

    def find_sims(self, *args, ownership: str | None = None, **kwargs) -> list[PremadeSim]:
        """Filter pre-made Sims, optionally by owned, unowned, or unknown."""
        if ownership not in (None, "owned", "unowned", "unknown"):
            raise PackStatusError(f"invalid ownership filter: {ownership!r}")
        sims = self.static_data().find_sims(*args, **kwargs)
        return sims if ownership is None else [sim for sim in sims if self.sim_ownership(sim) == ownership]

    def find_ancestors(self, *args, **kwargs) -> list[PremadeAncestor]:
        """Filter pre-made ancestors; see :meth:`PremadeBundle.find_ancestors`."""
        return self.static_data().find_ancestors(*args, **kwargs)

    def find_households(self, *args, **kwargs) -> list[PremadeHousehold]:
        """Filter pre-made households; see :meth:`PremadeBundle.find_households`."""
        return self.static_data().find_households(*args, **kwargs)

    def find_lots(self, *args, **kwargs) -> list[PremadeLot]:
        """Filter lots; see :meth:`PremadeBundle.find_lots`."""
        return self.static_data().find_lots(*args, **kwargs)

    @property
    def packs(self) -> list[str]:
        """Installed pack codes, or the packs represented in the catalog."""
        if self.installation is not None:
            return sorted({info.pack for info in self.installation.packages})
        return self.catalog.packs()

    def save_static(self, path: str | Path) -> Path:
        """Write a portable static-data snapshot and return its path."""
        return self.static_data().save(path)

    # ------------------------------------------------------------------
    # saves and Tray
    # ------------------------------------------------------------------
    def read_save(self, path: str | Path, catalog: Optional[Catalog] = None) -> SaveFile:
        return read_save(path, catalog if catalog is not None else self.catalog)

    def save_files(self) -> list[Path]:
        if self.user_dir is None:
            return []
        saves = Path(self.user_dir) / "saves"
        if not saves.is_dir():
            return []
        return sorted(saves.glob("*.save"))

    def latest_save_path(self) -> Optional[Path]:
        """Return the most recently modified ``.save`` file, if any."""
        files = self.save_files()
        if not files:
            return None
        return max(files, key=lambda path: path.stat().st_mtime)

    def latest_save(self) -> Optional[SaveFile]:
        """Read the most recently modified save, if any."""
        path = self.latest_save_path()
        return self.read_save(path) if path is not None else None

    def read_saves(self) -> list[SaveFile]:
        return [self.read_save(path) for path in self.save_files()]

    def tray_library(
        self,
        folder: str | Path | None = None,
        catalog: Optional[Catalog] = None,
    ) -> TrayLibrary:
        if folder is None:
            if self.user_dir is None:
                raise FileNotFoundError("no Sims 4 user directory; pass folder explicitly")
            folder = Path(self.user_dir) / "Tray"
        return read_tray_library(
            folder,
            catalog if catalog is not None else self.catalog,
        )

    # ------------------------------------------------------------------
    # icons / images
    # ------------------------------------------------------------------
    def icon_for(self, key: object) -> Optional["GameImage"]:
        """Return the tuning icon for a catalog model, key, or key string.

        Accepts anything with an ``icon``/``icon_key`` (Trait, Aspiration,
        AspirationTrack, CareerTrack, Milestone, RelationshipBit) or
        ``thumbnail``/``thumbnail_key`` (PremadeAncestor), plus raw
        ``ResourceKey`` and ``"TTTT:GGGG:IIII"`` strings.  Returns ``None``
        without an installation or when the image is absent.
        """
        if self.installation is None:
            return None
        return self.installation.read_image(key)

    def icon_bytes(self, key: object) -> Optional[bytes]:
        """Return raw icon bytes (DDS or PNG) for ``key``, if resolvable."""
        image = self.icon_for(key)
        return image.data if image is not None else None

    def icon_png(self, key: object) -> Optional[bytes]:
        """Return a tuning icon as PNG bytes, or ``None`` if unavailable."""
        image = self.icon_for(key)
        return image.to_png() if image is not None else None

    # ------------------------------------------------------------------
    # wiki validation
    # ------------------------------------------------------------------
    def validate_wiki(
        self,
        *,
        client=None,
        cache_dir: str | Path | None = None,
        sim_limit: int = 50,
        save: str | Path | SaveFile | None = None,
        catalog_only: bool = False,
    ):
        """Compare the SDK with The Sims Wiki (requires the validation extra)."""
        from .validation import WikiClient, run_validation

        static = self.static_data()
        if client is None:
            client = WikiClient(cache_dir=cache_dir)

        save_obj = None
        if not catalog_only:
            if isinstance(save, SaveFile):
                save_obj = save
            elif save is not None:
                save_obj = self.read_save(save, static.catalog)
            else:
                files = self.save_files()
                if files:
                    save_obj = self.read_save(files[0], static.catalog)

        return run_validation(
            static_data=static,
            client=client,
            sim_limit=sim_limit,
            save=save_obj,
            catalog_only=catalog_only,
        )

    # ------------------------------------------------------------------
    # misc
    # ------------------------------------------------------------------
    def refresh(self) -> StaticData:
        return self.static_data(refresh=True)

    def __repr__(self) -> str:
        return (
            f"Sims4Workspace(installation={self.installation!r}, "
            f"user_dir={self.user_dir!s})"
        )
