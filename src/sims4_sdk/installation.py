"""Locating packages and resources for a Sims 4 installation.

This module is deliberately save-agnostic: it describes the installed game
(base game, every DLC pack) plus optional mods, and gives the catalog builder a
deterministic load order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .core import DBPF, ResourceEntry, ResourceKey
from .core.resource_types import SIMOUTFIT_TYPE_ID
from .paths import find_install_dir, find_user_dir, iter_pack_folders, iter_pack_root_folders

__all__ = ["PackageInfo", "Installation", "PACK_PATTERN"]

PACK_PATTERN = re.compile(r"(EP|GP|SP|FP)\d+")

#: SimInfo resources (the ``.siminfo`` payload referenced by premade templates).
SIMINFO_TYPE_ID = SIMOUTFIT_TYPE_ID


def _package_priority(path: Path) -> int:
    name = path.name
    if "FullBuild" in name:
        return 0
    if "Preload" in name:
        return 1
    if "Delta" in name:
        return 2
    return 3


@dataclass(frozen=True)
class PackageInfo:
    path: Path
    pack: str
    is_mod: bool = False

    @property
    def label(self) -> str:
        if self.is_mod:
            return f"MOD:{self.path.name}"
        return self.pack

    def __repr__(self) -> str:
        return f"PackageInfo({self.path.name!r}, pack={self.pack!r}, mod={self.is_mod})"


class Installation:
    """A discovered Sims 4 game + user data installation."""

    def __init__(
        self,
        install_dir: str | Path | None = None,
        user_dir: str | Path | None = None,
        locale: str = "ENG_US",
        include_mods: bool = True,
    ):
        resolved = find_install_dir(install_dir)
        if resolved is None:
            raise FileNotFoundError(
                "could not find The Sims 4 installation; pass install_dir or set "
                "SIMS4_INSTALL_DIR"
            )
        self.install_dir = Path(resolved)
        self.user_dir = Path(user_dir) if user_dir is not None else find_user_dir()
        self.locale = locale
        self.include_mods = include_mods
        self._simo_index: Optional[dict[int, tuple[PackageInfo, ResourceEntry]]] = None
        self._image_index: Optional[dict[tuple[int, int], tuple[PackageInfo, ResourceEntry]]] = None

    # ------------------------------------------------------------------
    # package discovery
    # ------------------------------------------------------------------
    def _classify(self, path: Path) -> PackageInfo:
        try:
            relative = path.relative_to(self.install_dir)
        except ValueError:
            return PackageInfo(path, pack="MOD", is_mod=True)

        parts = relative.parts
        if parts and parts[0] == "Delta" and len(parts) > 1:
            return PackageInfo(path, pack=parts[1])
        if parts and parts[0] == "Data":
            return PackageInfo(path, pack="BASE")
        if parts and PACK_PATTERN.fullmatch(parts[0]):
            return PackageInfo(path, pack=parts[0])
        return PackageInfo(path, pack="MOD", is_mod=True)

    @property
    def base_packages(self) -> list[PackageInfo]:
        """Base-game packages in load order.

        The simulation build carries tuning; the client build carries the
        pre-made household and lot-manifest resources that tuning does not
        describe (see :mod:`sims4_sdk.catalog.worlds`).  Both are scanned so
        older-pack pre-mades such as the BFF household are visible.
        """
        result: list[PackageInfo] = []
        for folder in (self.install_dir / "Data" / "Simulation", self.install_dir / "Data" / "Client"):
            paths = sorted(folder.glob("*.package"), key=lambda p: (_package_priority(p), p.name))
            result.extend(PackageInfo(path, pack="BASE") for path in paths)
        return result

    @property
    def pack_packages(self) -> list[PackageInfo]:
        result: list[PackageInfo] = []
        for pack_dir in (*iter_pack_root_folders(self.install_dir), *iter_pack_folders(self.install_dir)):
            paths = sorted(pack_dir.glob("*.package"), key=lambda p: (_package_priority(p), p.name))
            for path in paths:
                result.append(PackageInfo(path, pack=pack_dir.name))
        return result

    @property
    def mod_packages(self) -> list[PackageInfo]:
        if not self.include_mods or self.user_dir is None:
            return []
        mods = Path(self.user_dir) / "Mods"
        if not mods.is_dir():
            return []
        result = [
            PackageInfo(path, pack="MOD", is_mod=True)
            for path in sorted(mods.rglob("*.package"))
        ]
        return result

    @property
    def packages(self) -> list[PackageInfo]:
        """Packages in load order: base, packs, then mods."""
        return self.base_packages + self.pack_packages + self.mod_packages

    @property
    def string_packages(self) -> list[PackageInfo]:
        """Packages that may contain STBL resources for the selected locale."""
        result: list[PackageInfo] = []

        base = self.install_dir / "Data" / "Client" / f"Strings_{self.locale}.package"
        if base.exists():
            result.append(PackageInfo(base, pack="BASE"))

        for pack_dir in (*iter_pack_root_folders(self.install_dir), *iter_pack_folders(self.install_dir)):
            candidate = pack_dir / f"Strings_{self.locale}.package"
            if candidate.exists():
                result.append(PackageInfo(candidate, pack=pack_dir.name))

        # Mods can add strings; scan every mod package for STBLs.
        result.extend(self.mod_packages)
        return result

    # ------------------------------------------------------------------
    # resource lookup
    # ------------------------------------------------------------------
    def siminfo_index(self) -> dict[int, tuple[PackageInfo, ResourceEntry]]:
        """Map SimInfo instance IDs to their package entry (mods win)."""
        if self._simo_index is None:
            index: dict[int, tuple[PackageInfo, ResourceEntry]] = {}
            for info in self.packages:
                package = DBPF(info.path)
                for entry in package.iter_entries(type_id=SIMINFO_TYPE_ID):
                    index[entry.key.instance] = (info, entry)
            self._simo_index = index
        return self._simo_index

    def find_siminfo(self, instance: int) -> Optional[bytes]:
        """Read a SimInfo resource by instance ID, or return ``None``."""
        found = self.siminfo_index().get(instance)
        if found is None:
            return None
        info, entry = found
        # The index entry already has the offset/size/compression, so read it
        # directly instead of re-parsing the package index for every Sim.
        return DBPF.read_entry(info.path, entry)

    def read_resource(self, info: PackageInfo, entry: ResourceEntry) -> bytes:
        return DBPF.read_entry(info.path, entry)

    def image_index(self) -> dict[tuple[int, int], tuple[PackageInfo, ResourceEntry]]:
        """Map ``(group, instance)`` to its image entry (mods win).

        Tuning icon keys use type ``0x2F7D0004`` but the bytes usually live
        in the ``0x00B2D882`` DST resource with the same group/instance, so
        the index is keyed without the type.
        """
        if self._image_index is None:
            from .core.resource_types import ICON_IMAGE_TYPE_IDS

            index: dict[tuple[int, int], tuple[PackageInfo, ResourceEntry]] = {}
            for info in self.packages:
                try:
                    package = DBPF(info.path)
                except Exception:
                    continue
                for entry in package.iter_entries_for_types(ICON_IMAGE_TYPE_IDS):
                    if entry.is_null:
                        continue
                    index[(entry.key.group, entry.key.instance)] = (info, entry)
            self._image_index = index
        return self._image_index

    def find_image_entry(
        self, group: int, instance: int
    ) -> Optional[tuple[PackageInfo, ResourceEntry]]:
        """Return the image entry for ``(group, instance)``, if any."""
        return self.image_index().get((group, instance))

    def read_image(self, key: object) -> Optional["GameImage"]:
        """Read a tuning icon/thumbnail by key, string, or icon-bearing model.

        Accepts a :class:`ResourceKey`, a ``"TTTT:GGGG:IIII"`` string, or any
        model with an ``icon`` / ``thumbnail`` / ``icon_key`` attribute.
        Returns a :class:`GameImage` (unshuffled DDS or PNG bytes plus size
        metadata), or ``None`` when the key is missing/unresolvable.
        """
        from .core.dbpf import ResourceKey
        from .core.images import decode_image, parse_image_key

        resource_key: Optional[ResourceKey] = None
        if isinstance(key, ResourceKey):
            resource_key = key
        elif isinstance(key, str):
            resource_key = parse_image_key(key)
        else:
            for attr in ("icon_key", "thumbnail_key", "icon", "thumbnail"):
                value = getattr(key, attr, None)
                if isinstance(value, ResourceKey):
                    resource_key = value
                    break
                if isinstance(value, str):
                    parsed = parse_image_key(value)
                    if parsed is not None:
                        resource_key = parsed
                        break
        if resource_key is None:
            return None
        found = self.find_image_entry(resource_key.group, resource_key.instance)
        if found is None:
            # Fall back to an exact type/group/instance match.
            raw = self.find_resource(
                resource_key.type_id, resource_key.group, resource_key.instance
            )
            if raw is None:
                return None
            try:
                return decode_image(resource_key, raw)
            except Exception:
                return None
        info, entry = found
        try:
            raw = DBPF.read_entry(info.path, entry)
            return decode_image(entry.key, raw)
        except Exception:
            return None

    def read_icon(self, icon: object) -> Optional["GameImage"]:
        """Alias for :meth:`read_image` for tuning ``icon`` fields."""
        return self.read_image(icon)

    def find_resource(
        self,
        type_id: int,
        group: int,
        instance: int,
    ) -> Optional[bytes]:
        """Read an arbitrary resource by key.

        This is intentionally a linear search over package indexes; it is fine
        for occasional lookups but not for bulk extraction.
        """
        key = ResourceKey(type_id, group, instance)
        for info in reversed(self.packages):
            package = DBPF(info.path)
            entry = package.find_entry(key)
            if entry is not None:
                return package.read_resource(entry)
        return None

    # ------------------------------------------------------------------
    # misc
    # ------------------------------------------------------------------
    def iter_packages(self, *, include_mods: bool = True) -> Iterator[PackageInfo]:
        for info in self.packages:
            if info.is_mod and not include_mods:
                continue
            yield info

    def __repr__(self) -> str:
        return (
            f"Installation({self.install_dir!s}, locale={self.locale!r}, "
            f"packages={len(self.packages)}, mods={self.include_mods})"
        )
