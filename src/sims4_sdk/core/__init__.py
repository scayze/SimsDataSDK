"""Low-level readers for The Sims 4 binary formats."""

from .combined_tuning import (
    CombinedTuning,
    CombinedTuningError,
    TuningElement,
    decode_binary_tuning,
    decode_binary_tuning_tree,
    is_binary_tuning,
)
from .data_tables import (
    DataTableError,
    DataTables,
    DataType,
    Schema,
    SchemaColumn,
    TableInfo,
    TableRows,
)
from .dbpf import (
    COMPRESSION_NONE,
    COMPRESSION_REFPACK,
    COMPRESSION_ZLIB,
    DBPF,
    DBPFError,
    DBPFHeader,
    ResourceEntry,
    ResourceKey,
)
from .fnv import fnv1_32, fnv1_64, fnv1a_32, fnv1a_64, hash32, hash64
from .images import (
    GameImage,
    ImageError,
    decode_image,
    dst_to_dds,
    dds_info,
    parse_icon_key,
    parse_image_key,
)
from .refpack import RefPackError, decompress as decompress_refpack, is_refpack
from .resource_types import (
    CAS_THUMBNAIL_TYPE_ID,
    COMBINED_TUNING_TYPE_ID,
    DST_IMAGE_ALT_TYPE_ID,
    DST_IMAGE_TYPE_ID,
    ICON_IMAGE_TYPE_IDS,
    LOT_MANIFEST_TYPE_ID,
    PNG_IMAGE_TYPE_ID,
    PREMADE_HOUSEHOLD_TYPE_ID,
    RLE_IMAGE_TYPE_ID,
    SIMDATA_TYPE_ID,
    STRING_TABLE_TYPE_ID,
    THUMBNAIL_TYPE_ID,
    TRAYITEM_TYPE_ID,
    TUNING_TYPE_ID,
    RESOURCE_TYPE_LABELS,
    type_name,
)
from .simdata import SimData, SimDataError
from .stbl import (
    LOCALE_CODES,
    STBLError,
    StringTable,
    locale_from_instance,
    locale_name,
)

__all__ = [
    # containers
    "DBPF",
    "DBPFError",
    "DBPFHeader",
    "ResourceEntry",
    "ResourceKey",
    # compression
    "COMPRESSION_NONE",
    "COMPRESSION_REFPACK",
    "COMPRESSION_ZLIB",
    "RefPackError",
    "decompress_refpack",
    "is_refpack",
    # string tables
    "StringTable",
    "STBLError",
    "LOCALE_CODES",
    "locale_from_instance",
    "locale_name",
    # tuning
    "CombinedTuning",
    "CombinedTuningError",
    "TuningElement",
    "decode_binary_tuning",
    "decode_binary_tuning_tree",
    "is_binary_tuning",
    # data tables
    "DataTables",
    "DataTableError",
    "DataType",
    "TableInfo",
    "TableRows",
    "Schema",
    "SchemaColumn",
    # simdata
    "SimData",
    "SimDataError",
    # images / icons
    "GameImage",
    "ImageError",
    "decode_image",
    "dst_to_dds",
    "dds_info",
    "parse_image_key",
    "parse_icon_key",
    # hashing
    "fnv1_32",
    "fnv1_64",
    "fnv1a_32",
    "fnv1a_64",
    "hash32",
    "hash64",
    # resource types
    "COMBINED_TUNING_TYPE_ID",
    "CAS_THUMBNAIL_TYPE_ID",
    "DST_IMAGE_TYPE_ID",
    "DST_IMAGE_ALT_TYPE_ID",
    "ICON_IMAGE_TYPE_IDS",
    "PNG_IMAGE_TYPE_ID",
    "RLE_IMAGE_TYPE_ID",
    "THUMBNAIL_TYPE_ID",
    "LOT_MANIFEST_TYPE_ID",
    "PREMADE_HOUSEHOLD_TYPE_ID",
    "SIMDATA_TYPE_ID",
    "STRING_TABLE_TYPE_ID",
    "TRAYITEM_TYPE_ID",
    "TUNING_TYPE_ID",
    "RESOURCE_TYPE_LABELS",
    "type_name",
]
