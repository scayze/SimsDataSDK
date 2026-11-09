"""Save-independent static catalog and pre-made Sim extraction."""

from .builder import build_catalog, cache_key, collect_entries, extract_catalog
from .models import (
    Aspiration,
    AspirationCategory,
    AspirationTrack,
    Career,
    CareerLevel,
    CareerTrack,
    Catalog,
    Milestone,
    Preference,
    RelationshipBit,
    SkillLevel,
    Trait,
    TuningSource,
)
from .premades import (
    HouseholdMember,
    HouseholdRelationship,
    PremadeAncestor,
    PremadeBundle,
    PremadeHousehold,
    PremadeSim,
    build_premades,
    parse_resource_key,
)
from .static import StaticData, build_static, load_static

__all__ = [
    # build
    "build_catalog",
    "build_static",
    "load_static",
    "collect_entries",
    "extract_catalog",
    "cache_key",
    # static container
    "StaticData",
    # models
    "Catalog",
    "Trait",
    "Preference",
    "Aspiration",
    "AspirationTrack",
    "AspirationCategory",
    "Career",
    "CareerTrack",
    "CareerLevel",
    "Milestone",
    "RelationshipBit",
    "SkillLevel",
    "TuningSource",
    # premades
    "PremadeSim",
    "PremadeHousehold",
    "PremadeAncestor",
    "PremadeBundle",
    "HouseholdMember",
    "HouseholdRelationship",
    "build_premades",
    "parse_resource_key",
]
