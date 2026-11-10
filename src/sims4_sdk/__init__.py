"""sims4-sdk — read The Sims 4 game data, saves, and Tray files.

The SDK exposes:

* :class:`sims4_sdk.Sims4Workspace` — discover the game and load everything
* :class:`sims4_sdk.catalog.Catalog` — traits, preferences, aspirations,
  careers, milestones, and relationship bits
* :class:`sims4_sdk.catalog.PremadeSim` — pre-made Sims and their base values
* :class:`sims4_sdk.catalog.PremadeHousehold` — households (tuning templates
  plus the starter-save resources used by older packs)
* :class:`sims4_sdk.catalog.PremadeLot` — lots and their occupying household
* :class:`sims4_sdk.save.SaveFile` — live save state (traits, careers, skills,
  family, milestones, pregnancy, occult, …)
* :class:`sims4_sdk.save.TrayLibrary` — Gallery/Tray households
* :mod:`sims4_sdk.validation` — cached Sims Wiki fetching, parsing, and
  reconciliation (requires the ``validation`` extra)
* :class:`sims4_sdk.core.DBPF` — package/world/save container reader
* :class:`sims4_sdk.core.StringTable` — localized STBL strings
* :class:`sims4_sdk.core.CombinedTuning` — XML or binary tuning blobs
* :class:`sims4_sdk.core.SimData` — binary DATA resources
* :mod:`sims4_sdk.paths` — installation and user-directory discovery
"""

from __future__ import annotations

from . import catalog, core, paths
from .catalog import (
    Aspiration,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    LotRecord,
    Milestone,
    Preference,
    PremadeAncestor,
    PremadeBundle,
    PremadeHousehold,
    PremadeLot,
    PremadeSim,
    RelationshipBit,
    SkillLevel,
    StarterCareer,
    StarterHouseholdRecord,
    StarterMember,
    StarterRelation,
    StaticData,
    Trait,
    WorldData,
    WorldDataError,
    build_catalog,
    build_static,
)
from .core import (
    COMBINED_TUNING_TYPE_ID,
    COMPRESSION_NONE,
    COMPRESSION_REFPACK,
    COMPRESSION_ZLIB,
    LOT_MANIFEST_TYPE_ID,
    PREMADE_HOUSEHOLD_TYPE_ID,
    SIMDATA_TYPE_ID,
    STRING_TABLE_TYPE_ID,
    TUNING_TYPE_ID,
    CombinedTuning,
    CombinedTuningError,
    DataTableError,
    DataTables,
    DBPF,
    DBPFError,
    DataType,
    RefPackError,
    ResourceEntry,
    ResourceKey,
    SimData,
    SimDataError,
    StringTable,
    STBLError,
    TuningElement,
    decode_binary_tuning,
    decompress_refpack,
    fnv1_32,
    fnv1_64,
    hash32,
    hash64,
    is_binary_tuning,
    is_refpack,
)
from .installation import Installation, PackageInfo
from .paths import (
    find_install_dir,
    find_user_dir,
    iter_pack_folders,
    iter_packages,
    iter_string_packages,
    mods_dir,
    saves_dir,
    tray_dir,
)
from .save import (
    SaveError,
    SaveFile,
    SavedHousehold,
    SavedSim,
    TrayError,
    TrayHousehold,
    TrayItem,
    TrayLibrary,
    read_save,
    read_tray_library,
)
from .siminfo import SimInfo, SimInfoError
from .workspace import Sims4Workspace

__version__ = "0.6.0"

__all__ = [
    "__version__",
    "core",
    "paths",
    "catalog",
    "Sims4Workspace",
    "Installation",
    "PackageInfo",
    "StaticData",
    "Catalog",
    "Trait",
    "Preference",
    "Aspiration",
    "AspirationTrack",
    "Career",
    "CareerTrack",
    "CareerLevel",
    "Milestone",
    "RelationshipBit",
    "SkillLevel",
    "PremadeSim",
    "PremadeHousehold",
    "PremadeAncestor",
    "PremadeLot",
    "PremadeBundle",
    "WorldData",
    "WorldDataError",
    "LotRecord",
    "StarterCareer",
    "StarterHouseholdRecord",
    "StarterMember",
    "StarterRelation",
    "build_catalog",
    "build_static",
    "SimInfo",
    "SimInfoError",
    "SaveFile",
    "SavedSim",
    "SavedHousehold",
    "TrayLibrary",
    "TrayHousehold",
    "TrayItem",
    "read_save",
    "read_tray_library",
    "SaveError",
    "TrayError",
    # containers
    "DBPF",
    "DBPFError",
    "ResourceEntry",
    "ResourceKey",
    # compression
    "COMPRESSION_NONE",
    "COMPRESSION_REFPACK",
    "COMPRESSION_ZLIB",
    "RefPackError",
    "decompress_refpack",
    "is_refpack",
    # strings
    "StringTable",
    "STBLError",
    "STRING_TABLE_TYPE_ID",
    # tuning
    "CombinedTuning",
    "CombinedTuningError",
    "TuningElement",
    "TUNING_TYPE_ID",
    "COMBINED_TUNING_TYPE_ID",
    "LOT_MANIFEST_TYPE_ID",
    "PREMADE_HOUSEHOLD_TYPE_ID",
    "decode_binary_tuning",
    "is_binary_tuning",
    # data tables / simdata
    "DataTables",
    "DataTableError",
    "DataType",
    "SimData",
    "SimDataError",
    "SIMDATA_TYPE_ID",
    # hashing
    "fnv1_32",
    "fnv1_64",
    "hash32",
    "hash64",
    # paths
    "find_install_dir",
    "find_user_dir",
    "iter_pack_folders",
    "iter_packages",
    "iter_string_packages",
    "saves_dir",
    "tray_dir",
    "mods_dir",
]
