"""Discovery helpers for The Sims 4 installation and user directories.

Nothing here is required by the binary readers; these helpers simply save every
downstream tool from re-implementing platform-specific path guessing.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Optional

__all__ = [
    "is_install_dir",
    "is_user_dir",
    "find_install_dir",
    "find_user_dir",
    "steam_libraries",
    "iter_packages",
    "iter_string_packages",
    "iter_pack_folders",
    "saves_dir",
    "tray_dir",
    "mods_dir",
]

ENV_INSTALL = "SIMS4_INSTALL_DIR"
ENV_USER = "SIMS4_USER_DIR"

_STEAM_COMMON = Path(r"C:\Program Files (x86)\Steam\steamapps\common\The Sims 4")
_EA_COMMON = Path(r"C:\Program Files\EA Games\The Sims 4")
_LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", r"C:\Program Files"))

_INSTALL_CANDIDATES = (
    _STEAM_COMMON,
    _EA_COMMON,
    Path(r"D:\SteamLibrary\steamapps\common\The Sims 4"),
    Path(r"E:\SteamLibrary\steamapps\common\The Sims 4"),
    Path(r"F:\SteamLibrary\steamapps\common\The Sims 4"),
    Path(r"G:\SteamLibrary\steamapps\common\The Sims 4"),
    Path(r"I:\Games\SteamLibrary\steamapps\common\The Sims 4"),
    _LOCAL_APP_DATA / "EA Games" / "The Sims 4",
)

_STEAM_ROOTS = (
    Path(r"C:\Program Files (x86)\Steam"),
    Path(r"C:\Program Files\Steam"),
)


def is_install_dir(path: str | Path) -> bool:
    """Return ``True`` if ``path`` looks like a Sims 4 installation."""
    path = Path(path)
    return (path / "Data" / "Simulation" / "SimulationFullBuild0.package").exists()


def is_user_dir(path: str | Path) -> bool:
    """Return ``True`` if ``path`` looks like a Sims 4 user data folder."""
    path = Path(path)
    return (path / "saves").exists() or (path / "Tray").exists()


def steam_libraries() -> list[Path]:
    """Return Steam library roots discovered from ``libraryfolders.vdf``."""
    libraries: list[Path] = []
    for root in _STEAM_ROOTS:
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in re.finditer(r'"path"\s*"([^"]+)"', text):
            path = Path(match.group(1).replace("\\\\", "\\"))
            if path not in libraries:
                libraries.append(path)
    return libraries


def find_install_dir(explicit: str | Path | None = None) -> Optional[Path]:
    """Locate the game installation directory.

    Priority: explicit argument, ``SIMS4_INSTALL_DIR``, known paths, then Steam
    library folders.
    """
    if explicit is not None:
        return Path(explicit)
    from_env = os.environ.get(ENV_INSTALL)
    if from_env:
        return Path(from_env)

    for candidate in _INSTALL_CANDIDATES:
        if is_install_dir(candidate):
            return candidate
    for library in steam_libraries():
        candidate = library / "steamapps" / "common" / "The Sims 4"
        if is_install_dir(candidate):
            return candidate
    return None


def find_user_dir(explicit: str | Path | None = None) -> Optional[Path]:
    """Locate the user data directory (saves, Tray, Mods, ...)."""
    if explicit is not None:
        return Path(explicit)
    from_env = os.environ.get(ENV_USER)
    if from_env:
        return Path(from_env)

    home = Path.home()
    candidates = [
        home / "Documents" / "Electronic Arts" / "The Sims 4",
        home / "OneDrive" / "Documents" / "Electronic Arts" / "The Sims 4",
        home / "OneDrive" / "Dokumente" / "Electronic Arts" / "The Sims 4",
        home / "Documents" / "EA Games" / "The Sims 4",
    ]
    for candidate in candidates:
        if is_user_dir(candidate):
            return candidate
    return None


def iter_pack_folders(install_dir: str | Path) -> Iterable[Path]:
    """Yield ``Delta/<PACK>`` folders (EP/GP/SP/FP) that exist."""
    delta = Path(install_dir) / "Delta"
    if not delta.is_dir():
        return
    for folder in sorted(delta.iterdir()):
        if folder.is_dir() and re.fullmatch(r"(EP|GP|SP|FP)\d+", folder.name):
            yield folder


def iter_packages(install_dir: str | Path, *, include_base: bool = True) -> Iterable[Path]:
    """Yield every ``.package`` file belonging to the game and its packs.

    This deliberately excludes user mods; add your own ``Mods`` scan on top.
    """
    install = Path(install_dir)
    if include_base:
        for folder in (
            install / "Data" / "Simulation",
            install / "Data" / "Client",
        ):
            if folder.is_dir():
                yield from sorted(folder.glob("*.package"))
    for pack in iter_pack_folders(install):
        yield from sorted(pack.glob("*.package"))


def iter_string_packages(
    install_dir: str | Path,
    locale: str = "ENG_US",
) -> Iterable[Path]:
    """Yield the localized ``Strings_<locale>.package`` files."""
    install = Path(install_dir)
    filename = f"Strings_{locale}.package"
    base = install / "Data" / "Client" / filename
    if base.exists():
        yield base
    for pack in iter_pack_folders(install):
        candidate = pack / filename
        if candidate.exists():
            yield candidate


def saves_dir(user_dir: str | Path) -> Path:
    return Path(user_dir) / "saves"


def tray_dir(user_dir: str | Path) -> Path:
    return Path(user_dir) / "Tray"


def mods_dir(user_dir: str | Path) -> Path:
    return Path(user_dir) / "Mods"
