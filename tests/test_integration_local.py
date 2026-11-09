"""Integration tests that read a real The Sims 4 installation.

These are skipped automatically when no installation is found.  Point
``SIMS4_INSTALL_DIR`` / ``SIMS4_USER_DIR`` at a specific folder to run them
against another machine's data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sims4_sdk.core import (
    COMBINED_TUNING_TYPE_ID,
    SIMDATA_TYPE_ID,
    STRING_TABLE_TYPE_ID,
    CombinedTuning,
    DBPF,
    SimData,
    StringTable,
)

pytestmark = pytest.mark.integration


def _require(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"missing {path}")
    return path


def test_base_delta_package_index(install_dir: Path) -> None:
    path = _require(install_dir / "Data" / "Simulation" / "SimulationDeltaBuild0.package")
    package = DBPF(path)

    assert package.header.major_version == 2
    assert len(package.entries) > 100_000
    types = {entry.key.type_id for entry in package.entries}
    assert STRING_TABLE_TYPE_ID in types or COMBINED_TUNING_TYPE_ID in types
    assert SIMDATA_TYPE_ID in types

    combined = list(package.iter_entries(type_id=COMBINED_TUNING_TYPE_ID))
    simdata = list(package.iter_entries(type_id=SIMDATA_TYPE_ID))
    assert len(combined) >= 1
    assert len(simdata) > 1000


def test_english_string_tables(install_dir: Path) -> None:
    path = _require(install_dir / "Data" / "Client" / "Strings_ENG_US.package")
    merged = StringTable()

    with DBPF(path) as package:
        tables = [
            StringTable.parse(package.read_resource(entry))
            for entry in package.iter_entries(type_id=STRING_TABLE_TYPE_ID)
        ]

    assert tables
    for table in tables:
        merged.update(table)

    assert len(merged) > 1000
    assert all(isinstance(value, str) for value in merged.values())


def test_combined_tuning_from_full_build(install_dir: Path) -> None:
    path = _require(install_dir / "Data" / "Simulation" / "SimulationFullBuild0.package")

    with DBPF(path) as package:
        entries = list(package.iter_entries(type_id=COMBINED_TUNING_TYPE_ID))
        assert entries, "expected a Combined Tuning resource in the full build"
        raw = package.read_resource(entries[0])

    assert raw[:1] in (b"<", b"\xef")  # XML (optionally BOM-prefixed)
    tuning = CombinedTuning.parse(raw)

    assert len(tuning) > 1000
    assert tuning.by_class("Trait"), "expected Trait tuning entries"


def test_combined_tuning_from_binary_delta(install_dir: Path) -> None:
    path = _require(install_dir / "Delta" / "EP13" / "SimulationDeltaBuild0.package")

    with DBPF(path) as package:
        entries = list(package.iter_entries(type_id=COMBINED_TUNING_TYPE_ID))
        assert entries, "expected a Combined Tuning resource in EP13"
        raw = package.read_resource(entries[0])

    assert raw[:4] == b"DATA"
    tuning = CombinedTuning.parse(raw)

    assert len(tuning) > 100
    assert all(entry.name for entry in tuning.entries[:50])
    assert tuning.index_by_instance_id()


def test_simdata_resource(install_dir: Path) -> None:
    path = _require(install_dir / "Data" / "Simulation" / "SimulationDeltaBuild0.package")

    with DBPF(path) as package:
        entry = next(package.iter_entries(type_id=SIMDATA_TYPE_ID))
        raw = package.read_resource(entry)

    assert raw[:4] == b"DATA"
    simdata = SimData.parse(raw)
    assert simdata.version in (0x100, 0x101)
    assert simdata.tables.tables
    assert simdata.table_names()
    assert "DATA version" in simdata.describe()


def test_save_file_uses_constant_group_index(user_dir: Path) -> None:
    saves = sorted((user_dir / "saves").glob("*.save"))
    if not saves:
        pytest.skip("no save files in the user directory")

    package = DBPF(saves[0])
    assert package.header.major_version == 2
    assert package.entries
    assert package.index_flags & 0x02, "save indexes normally store the group once"

    # Every non-null entry must be readable (this exercises zlib and RefPack).
    readable = 0
    for entry in package.entries:
        if entry.is_null:
            continue
        package.read_resource(entry)
        readable += 1
    assert readable > 0
