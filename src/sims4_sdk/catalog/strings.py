"""Merged localized strings for the static catalog."""

from __future__ import annotations

from typing import Optional

from ..core import DBPF, STRING_TABLE_TYPE_ID, StringTable, locale_from_instance
from ..core.stbl import LOCALE_CODES
from ..installation import Installation, PackageInfo
from .diagnostics import ExtractionIssue

__all__ = ["locale_code", "load_strings"]

_LOCALE_CODES_BY_NAME = {name: code for code, name in LOCALE_CODES.items()}


def locale_code(locale: str) -> int:
    name = locale.strip().upper()
    if name in _LOCALE_CODES_BY_NAME:
        return _LOCALE_CODES_BY_NAME[name]
    # Allow a numeric byte like "0x00" or "0".
    try:
        return int(name, 0)
    except ValueError as exc:
        raise ValueError(f"unknown Sims 4 locale {locale!r}") from exc


def load_strings(
    installation: Installation,
    *,
    packages: Optional[list[PackageInfo]] = None,
    diagnostics: Optional[list[ExtractionIssue]] = None,
) -> dict[int, str]:
    """Merge STBL strings from the base game, packs, and mods.

    Later packages win, matching the catalog's load order (mods last).
    """
    wanted = locale_code(installation.locale)
    merged: dict[int, str] = {}
    sources = packages if packages is not None else installation.string_packages

    for info in sources:
        try:
            package = DBPF(info.path)
        except Exception as exc:
            if diagnostics is not None:
                diagnostics.append(ExtractionIssue.from_exception(
                    "string_package_open", exc, package_path=str(info.path)
                ))
            continue
        for entry in package.iter_entries(type_id=STRING_TABLE_TYPE_ID):
            if info.is_mod:
                code = locale_from_instance(entry.key.instance)
                # Some mods use arbitrary instance IDs; only filter when the
                # high byte is a known locale.
                if code in LOCALE_CODES and code != wanted:
                    continue
            try:
                table = StringTable.parse(package.read_resource(entry))
            except Exception as exc:
                # A broken user mod should not prevent catalog extraction.
                if diagnostics is not None:
                    diagnostics.append(ExtractionIssue.from_exception(
                        "string_table", exc, package_path=str(info.path), resource_key=entry.key
                    ))
                continue
            merged.update(table.entries)
    return merged
