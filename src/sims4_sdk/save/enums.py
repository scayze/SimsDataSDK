"""Enums used by save and Tray data."""

from __future__ import annotations

from typing import Iterable

__all__ = [
    "AGE_NAMES",
    "GENDER_NAMES",
    "SPECIES_NAMES",
    "OCCULT_FLAGS",
    "FAMILY_RELATION_NAMES",
    "name_for",
    "names_for_flags",
]

# From sims/sim_info_types.py
AGE_NAMES = {
    1: "BABY",
    2: "TODDLER",
    4: "CHILD",
    8: "TEEN",
    16: "YOUNGADULT",
    32: "ADULT",
    64: "ELDER",
    128: "INFANT",
}

GENDER_NAMES = {
    4096: "MALE",
    8192: "FEMALE",
}

SPECIES_NAMES = {
    1: "HUMAN",
    2: "DOG",
    3: "CAT",
    4: "SMALLDOG",
    5: "FOX",
    6: "HORSE",
}

# Directional bits: the target is respectively the actor's owner or pet.
PET_OWNER_BITS = frozenset({148060, 148062, 321335})
PET_OWNED_BITS = frozenset({148061, 148063, 321334})

# From sims/occult/occult_enums.py (IntFlags)
OCCULT_FLAGS = {
    1: "HUMAN",
    2: "ALIEN",
    4: "VAMPIRE",
    8: "MERMAID",
    16: "WITCH",
    32: "WEREWOLF",
    64: "FAIRY",
}

# From sims/sim_info_types.py / RelationshipIndex
FAMILY_RELATION_NAMES = {
    0: "MOTHER",
    1: "FATHER",
    2: "MOTHERS_MOM",
    3: "MOTHERS_FATHER",
    4: "FATHERS_MOM",
    5: "FATHERS_FATHER",
    6: "NONE",
    7: "PARENT",
    8: "SIBLING",
    9: "SPOUSE",
    10: "FIANCE",
    11: "UNUSED2",
    12: "DESCENDANT",
    13: "GRANDPARENT",
    14: "GRANDCHILD",
    15: "SIBLINGS_CHILDREN",
    16: "PARENTS_SIBLING",
    17: "COUSIN",
}


def name_for(value: int, mapping: dict[int, str], default: str = "UNKNOWN") -> str:
    return mapping.get(value, f"{default}_{value}")


def names_for_flags(value: int, mapping: dict[int, str]) -> list[str]:
    return [name for flag, name in mapping.items() if value & flag]


def animal_classification(species: str | None) -> tuple[bool | None, bool | None]:
    """Return (is_animal, is_pet); unknown species stay unknown."""
    name = (species or "").casefold().replace("_", "")
    if name == "human":
        return False, False
    if name == "fox":
        return True, False
    if name in {"dog", "smalldog", "cat", "horse"}:
        return True, True
    return None, None
