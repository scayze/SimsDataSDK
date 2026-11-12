"""Known DBPF resource type IDs for The Sims 4.

Only the types that matter to this SDK are listed with full names; the rest are
kept here as a convenient reference because catalog extractors in later steps
look them up by name.
"""

from __future__ import annotations

from typing import Final

#: Individual tuning XML resources (``<I>`` elements).
TUNING_TYPE_ID: Final = 0x03B33DDF
#: One blob containing all tuning for a package (XML or binary ``DATA``).
COMBINED_TUNING_TYPE_ID: Final = 0x62E94D38
#: Localized string table.
STRING_TABLE_TYPE_ID: Final = 0x220557DA
#: Binary SimData / binary tuning companion (the ``DATA`` table format).
SIMDATA_TYPE_ID: Final = 0x545AC67A
#: SimInfo (a.k.a. SIMO) — baked Sim data / outfits.
SIMOUTFIT_TYPE_ID: Final = 0x025ED6F4
SIMINFO_TYPE_ID: Final = SIMOUTFIT_TYPE_ID
#: DST (shuffled DDS) image — the storage format for tuning icons.
DST_IMAGE_TYPE_ID: Final = 0x00B2D882
#: Alternate DST overlay image type.
DST_IMAGE_ALT_TYPE_ID: Final = 0xB6C8B6A0
#: PNG image — tuning icon keys use this type, but the bytes usually live
#: in the DST resource with the same group/instance.
PNG_IMAGE_TYPE_ID: Final = 0x2F7D0004
#: Compressed DDS variant.
RLE_IMAGE_TYPE_ID: Final = 0x3453CF95
#: Generic thumbnail image.
THUMBNAIL_TYPE_ID: Final = 0x9C925813
#: CAS part thumbnail image.
CAS_THUMBNAIL_TYPE_ID: Final = 0x3C1AF1F2
#: Image resource types that may hold a tuning icon's pixels.
ICON_IMAGE_TYPE_IDS: Final = frozenset(
    {DST_IMAGE_TYPE_ID, DST_IMAGE_ALT_TYPE_ID, PNG_IMAGE_TYPE_ID}
)
#: Tray item metadata.
TRAYITEM_TYPE_ID: Final = 0x2A8A5E22
#: Lot/household manifest used to build a new save (one record per lot).
LOT_MANIFEST_TYPE_ID: Final = 0x729F6C4F
#: Pre-made household / starter-save definition (protobuf, older pack range).
PREMADE_HOUSEHOLD_TYPE_ID: Final = 0xB3C438F0

#: Human-readable labels for the resource types this SDK understands.
RESOURCE_TYPE_LABELS: Final[dict[int, str]] = {
    TUNING_TYPE_ID: "Tuning XML",
    COMBINED_TUNING_TYPE_ID: "Combined Tuning",
    STRING_TABLE_TYPE_ID: "String Table (STBL)",
    SIMDATA_TYPE_ID: "SimData (DATA)",
    SIMOUTFIT_TYPE_ID: "SimInfo (SIMO)",
    TRAYITEM_TYPE_ID: "Tray Item",
    LOT_MANIFEST_TYPE_ID: "Lot/Household Manifest",
    PREMADE_HOUSEHOLD_TYPE_ID: "Pre-made Household",
    0x00B2D882: "DDS Image",
    0x0166038C: "Name Map",
    0x01661233: "Model (MODL)",
    0x01D10F34: "Model LOD (MLOD)",
    0x2F7D0004: "PNG Image",
    0x319E4F1D: "Object Catalog (COBJ)",
    0x3453CF95: "DDS DXT5 RLE Image",
    0x3C1AF1F2: "CAS Part Thumbnail",
    0x6B20C4F3: "Animation Clip (CLIP)",
    0x8EAF13DE: "Rig (RIG)",
    0x9C925813: "Thumbnail",
    0xBC4A5044: "Geometry Data",
    0xC0DB5AE7: "Object Definition (OBJD)",
    0xD3044521: "Slot",
    0xD382BF57: "Footprint (FTPT)",
}


def type_name(type_id: int) -> str:
    """Return a readable name for a resource type ID."""
    return RESOURCE_TYPE_LABELS.get(type_id, f"0x{type_id:08X}")
