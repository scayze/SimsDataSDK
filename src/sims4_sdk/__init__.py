"""sims4-sdk — read The Sims 4 game data, saves, and Tray files.

Step 1 exposes the binary foundation:

* :class:`sims4_sdk.core.DBPF` — package/world/save container reader
* :class:`sims4_sdk.core.StringTable` — localized STBL strings
* :class:`sims4_sdk.core.CombinedTuning` — XML or binary tuning blobs
* :class:`sims4_sdk.core.SimData` — binary DATA resources
* :mod:`sims4_sdk.paths` — installation and user-directory discovery
"""

from __future__ import annotations

from . import core, paths
from .core import (
    COMBINED_TUNING_TYPE_ID,
    COMPRESSION_NONE,
    COMPRESSION_REFPACK,
    COMPRESSION_ZLIB,
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

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "core",
    "paths",
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
