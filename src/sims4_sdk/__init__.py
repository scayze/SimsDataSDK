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
* :func:`sims4_sdk.to_dict` / :func:`sims4_sdk.to_json` — JSON-safe export of
  any model; every model also has ``.to_dict()`` and ``.to_json()``
* :class:`sims4_sdk.Sims4SDKError` — base class for every SDK exception

A static snapshot can be saved once and loaded on a machine without the game::

    from sims4_sdk import Sims4Workspace

    Sims4Workspace().save_static("sims4-static.pkl")

    offline = Sims4Workspace.from_static("sims4-static.pkl", user_dir="...")
    save = offline.read_save(offline.latest_save_path())
"""

from __future__ import annotations

from . import catalog, core, export, paths, save
from .catalog import (
    Aspiration,
    AspirationCategory,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    CatalogError,
    ExtractionIssue,
    GenderOptions,
    HouseholdMember,
    HouseholdRelationship,
    LotRecord,
    Milestone,
    PremadeAncestor,
    PremadeBundle,
    PremadeFamilyLink,
    PremadeHousehold,
    PremadeLot,
    PremadeRelationship,
    PremadeSim,
    Preference,
    RelationshipBit,
    RelationshipDefault,
    RelationshipTrackValue,
    SkillLevel,
    StarterCareer,
    StarterHouseholdRecord,
    StarterMember,
    StarterRelation,
    StaticData,
    StaticDataError,
    Trait,
    TuningSource,
    WorldData,
    WorldDataError,
    build_catalog,
    build_static,
    load_static,
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
    decode_binary_tuning_tree,
    decompress_refpack,
    fnv1_32,
    fnv1_64,
    hash32,
    hash64,
    is_binary_tuning,
    is_refpack,
)
from .exceptions import Sims4SDKError
from .export import Serializable, Sims4JSONEncoder, to_dict, to_json
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
    Artwork,
    ArtworkError,
    decode_artwork,
    read_tray_image,
    AGE_NAMES,
    FAMILY_RELATION_NAMES,
    GENDER_NAMES,
    OCCULT_FLAGS,
    SPECIES_NAMES,
    SaveAccount,
    SaveError,
    SaveFile,
    SaveNeighborhood,
    SaveSlot,
    SaveZone,
    SavedCareer,
    SavedCareerHistory,
    SavedFamilyRelation,
    SavedHousehold,
    SavedMilestone,
    SavedRelationship,
    SavedRelationshipTrack,
    SavedRelationshipTrope,
    SavedSim,
    SavedSkill,
    SavedStatistic,
    SavedTimedAspiration,
    TrayError,
    TrayHousehold,
    TrayItem,
    TrayLibrary,
    read_save,
    read_tray_library,
)
from .siminfo import SimInfo, SimInfoError
from .workspace import Sims4Workspace

__version__ = "0.9.0"

__all__ = [
    "__version__",
    # modules
    "core",
    "paths",
    "catalog",
    "save",
    "export",
    # facade
    "Sims4Workspace",
    "Installation",
    "PackageInfo",
    # errors
    "Sims4SDKError",
    # static data
    "StaticData",
    "StaticDataError",
    "Catalog",
    "CatalogError",
    "ExtractionIssue",
    "TuningSource",
    "Trait",
    "Preference",
    "Aspiration",
    "AspirationCategory",
    "AspirationTrack",
    "Career",
    "CareerTrack",
    "CareerLevel",
    "Milestone",
    "RelationshipBit",
    "RelationshipTrackValue",
    "RelationshipDefault",
    "PremadeRelationship",
    "GenderOptions",
    "SkillLevel",
    "PremadeSim",
    "PremadeHousehold",
    "PremadeAncestor",
    "PremadeLot",
    "PremadeBundle",
    "HouseholdMember",
    "HouseholdRelationship",
    "PremadeFamilyLink",
    "WorldData",
    "WorldDataError",
    "LotRecord",
    "StarterCareer",
    "StarterHouseholdRecord",
    "StarterMember",
    "StarterRelation",
    "build_catalog",
    "build_static",
    "load_static",
    "SimInfo",
    "SimInfoError",
    # save data
    "SaveFile",
    "Artwork",
    "ArtworkError",
    "decode_artwork",
    "read_tray_image",
    "SaveSlot",
    "SaveAccount",
    "SaveZone",
    "SaveNeighborhood",
    "SavedSim",
    "SavedHousehold",
    "SavedSkill",
    "SavedCareer",
    "SavedCareerHistory",
    "SavedRelationship",
    "SavedRelationshipTrack",
    "SavedRelationshipTrope",
    "SavedFamilyRelation",
    "SavedMilestone",
    "SavedTimedAspiration",
    "SavedStatistic",
    "read_save",
    "SaveError",
    "AGE_NAMES",
    "GENDER_NAMES",
    "SPECIES_NAMES",
    "OCCULT_FLAGS",
    "FAMILY_RELATION_NAMES",
    # Tray
    "TrayLibrary",
    "TrayHousehold",
    "TrayItem",
    "read_tray_library",
    "TrayError",
    # serialization
    "Serializable",
    "Sims4JSONEncoder",
    "to_dict",
    "to_json",
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
    "decode_binary_tuning_tree",
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
