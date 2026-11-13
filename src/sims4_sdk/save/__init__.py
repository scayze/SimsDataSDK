"""Save-file and Tray readers."""

from .artwork import Artwork, ArtworkError, decode_artwork, read_tray_image

from .enums import (
    AGE_NAMES,
    FAMILY_RELATION_NAMES,
    GENDER_NAMES,
    OCCULT_FLAGS,
    SPECIES_NAMES,
)
from .models import (
    SaveAccount,
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
    TrayHousehold,
    TrayItem,
    TrayLibrary,
)
from .protobuf import ProtobufError, decode, iter_fields
from .reader import SaveError, read_save, read_save_resource, sim_from_dict
from .tray import (TrayError, TrayListing, TrayListingGroup, list_tray_households,
                   read_household_binary, read_tray_item, read_tray_library)

__all__ = [
    "Artwork", "ArtworkError", "decode_artwork", "read_tray_image",
    # enums
    "AGE_NAMES",
    "GENDER_NAMES",
    "SPECIES_NAMES",
    "OCCULT_FLAGS",
    "FAMILY_RELATION_NAMES",
    # save models
    "SaveFile",
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
    # tray models
    "TrayItem",
    "TrayHousehold",
    "TrayLibrary",
    "TrayListing",
    "TrayListingGroup",
    "list_tray_households",
    # readers
    "read_save",
    "read_save_resource",
    "sim_from_dict",
    "read_tray_item",
    "read_household_binary",
    "read_tray_library",
    # errors
    "SaveError",
    "TrayError",
    "ProtobufError",
    # low-level
    "decode",
    "iter_fields",
]
