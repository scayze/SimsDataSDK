"""Portable snapshots, offline workspaces, and the exception hierarchy."""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from sims4_sdk import Sims4SDKError, Sims4Workspace
from sims4_sdk.catalog import (
    Career,
    Catalog,
    CatalogError,
    StaticData,
    StaticDataError,
    Trait,
    WorldDataError,
)
from sims4_sdk.catalog.premades import PremadeBundle, PremadeHousehold, PremadeSim
from sims4_sdk.core import (
    CombinedTuningError,
    DataTableError,
    DBPFError,
    RefPackError,
    SimDataError,
    STBLError,
)
from sims4_sdk.save import (
    ProtobufError,
    SaveError,
    TrayError,
    TrayHousehold,
    TrayItem,
    TrayLibrary,
)
from sims4_sdk.siminfo import SimInfoError
from sims4_sdk.validation.wiki_client import WikiError


def build_catalog() -> Catalog:
    return Catalog(
        traits={
            1: Trait(
                id=1,
                name="trait_Mean",
                display_name="Mean",
                description=None,
                trait_type="PERSONALITY",
            )
        },
        careers={2: Career(id=2, name="career_Test")},
        strings={0x10: "Hello"},
        tuning_names={3: "skill_Test"},
    ).finalize()


def build_static() -> StaticData:
    sim = PremadeSim(
        id=10,
        name="template_sim_Bella_Goth",
        first_name="Bella",
        last_name="Goth",
        household_id=20,
        household_name="Goth",
    )
    household = PremadeHousehold(id=20, name="Goth")
    return StaticData(
        catalog=build_catalog(),
        premades=PremadeBundle(sims=[sim], households=[household]),
    )


def test_catalog_save_load_round_trip(tmp_path: Path) -> None:
    catalog = build_catalog()
    target = catalog.save(tmp_path / "nested" / "catalog.pkl")

    assert target.exists()
    loaded = Catalog.load(target)

    assert loaded is not catalog
    assert loaded.trait("trait_mean").display_name == "Mean"
    assert loaded.career("CAREER_TEST").id == 2
    assert loaded.strings[0x10] == "Hello"
    assert loaded.tuning_names[3] == "skill_Test"
    # Indexes survive the round-trip.
    assert loaded.traits_by_name["trait_Mean"] is loaded.traits[1]


def test_catalog_load_rejects_foreign_files(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.pkl"
    garbage.write_bytes(b"not a pickle")

    with pytest.raises(CatalogError):
        Catalog.load(garbage)

    wrong_type = tmp_path / "wrong.pkl"
    wrong_type.write_bytes(pickle.dumps({"not": "a catalog"}))
    with pytest.raises(CatalogError):
        Catalog.load(wrong_type)

    with pytest.raises(CatalogError):
        Catalog.load(tmp_path / "missing.pkl")


def test_static_data_save_load_round_trip(tmp_path: Path) -> None:
    static = build_static()
    target = static.save(tmp_path / "sims4-static.pkl")

    loaded = StaticData.load(target)

    assert loaded is not static
    assert loaded.catalog.trait(1).name == "trait_Mean"
    assert loaded.sim("bella goth").id == 10
    assert loaded.household("goth").id == 20
    assert loaded.find_sims("goth")[0].full_name == "Bella Goth"


def test_older_household_snapshot_without_lot_ids_remains_readable(tmp_path: Path) -> None:
    static = build_static()
    del static.households[0].lot_ids
    loaded = StaticData.load(static.save(tmp_path / "old.pkl"))
    household = loaded.households[0]
    assert household.lot_ids == [] and household.lot_id is None
    assert household.to_dict()["lot_ids"] == []


def test_older_snapshots_without_world_and_diagnostics_remain_readable(tmp_path: Path) -> None:
    static = build_static()
    del static.world
    del static.catalog.diagnostics
    loaded = StaticData.load(static.save(tmp_path / "old-static.pkl"))
    assert loaded.world is None
    assert loaded.catalog.diagnostics == []
    assert loaded.to_dict()["world"] is None


def test_static_data_load_rejects_foreign_files(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.pkl"
    garbage.write_bytes(b"not a pickle")

    with pytest.raises(StaticDataError):
        StaticData.load(garbage)

    wrong_type = tmp_path / "wrong.pkl"
    wrong_type.write_bytes(pickle.dumps([1, 2, 3]))
    with pytest.raises(StaticDataError):
        StaticData.load(wrong_type)


def test_workspace_from_static_runs_without_installation(tmp_path: Path) -> None:
    snapshot = build_static().save(tmp_path / "sims4-static.pkl")
    user_dir = tmp_path / "The Sims 4"
    (user_dir / "saves").mkdir(parents=True)

    workspace = Sims4Workspace.from_static(snapshot, user_dir=user_dir)

    assert workspace.catalog.trait("TRAIT_MEAN").id == 1
    assert workspace.find_sim("bella").id == 10
    assert [sim.id for sim in workspace.find_sims("goth")] == [10]
    assert workspace.save_files() == []
    assert workspace.latest_save_path() is None
    assert workspace.latest_save() is None


def test_workspace_accepts_in_memory_static_data(tmp_path: Path) -> None:
    static = build_static()
    workspace = Sims4Workspace(static=static, user_dir=tmp_path)
    assert workspace.catalog.career(2).name == "career_Test"
    # The supplied snapshot is used as-is instead of rebuilding the catalog.
    assert workspace.static_data() is static
    # ``packs`` is always a concrete list, whether from the install or catalog.
    assert isinstance(workspace.packs, list)


def test_workspace_save_static_writes_snapshot(tmp_path: Path) -> None:
    workspace = Sims4Workspace(static=build_static(), user_dir=tmp_path)
    target = workspace.save_static(tmp_path / "exported.pkl")

    assert StaticData.load(target).sim("bella").id == 10


def test_workspace_from_static_requires_a_snapshot_or_installation(
    tmp_path: Path,
) -> None:
    # A missing snapshot file is reported as a snapshot error, not silently
    # swallowed as "offline mode".
    with pytest.raises(StaticDataError):
        Sims4Workspace.from_static(tmp_path / "missing.pkl", user_dir=tmp_path)


@pytest.mark.parametrize(
    "error",
    [
        DBPFError,
        RefPackError,
        STBLError,
        DataTableError,
        CombinedTuningError,
        SimDataError,
        SimInfoError,
        WorldDataError,
        SaveError,
        TrayError,
        ProtobufError,
        CatalogError,
        StaticDataError,
    ],
)
def test_value_errors_are_sdk_errors_and_value_errors(error) -> None:
    assert issubclass(error, Sims4SDKError)
    assert issubclass(error, ValueError)
    assert isinstance(error("boom"), Sims4SDKError)
    assert isinstance(error("boom"), ValueError)


def test_wiki_error_stays_a_runtime_error() -> None:
    assert issubclass(WikiError, Sims4SDKError)
    assert issubclass(WikiError, RuntimeError)
    assert not issubclass(WikiError, ValueError)


def test_tray_models_are_part_of_the_public_surface() -> None:
    library = TrayLibrary(
        items=[TrayItem(path=Path("a.trayitem"), item_id=1, title="A")],
        households=[
            TrayHousehold(path=Path("a.householdbinary"), family_name="Goth")
        ],
    )
    assert library.to_dict()["households"][0]["family_name"] == "Goth"
