"""Dictionary and JSON serialization for SDK models.

Every public model in ``sims4_sdk`` inherits from :class:`Serializable` and
therefore exposes ``to_dict()`` and ``to_json()``.  The output is JSON-safe:

* :class:`~pathlib.Path` becomes a string,
* ``bytes`` (hashes, raw payloads) become lowercase hex strings,
* :class:`~sims4_sdk.core.ResourceKey` becomes ``"TTTTTTTT!GGGGGGGG!IIIIIIIIIIIIIIII"``,
* computed properties such as ``full_name``, ``age``, ``gender_options``,
  ``personality_traits`` and ``likes`` are included,
* cross-references to catalog definitions are emitted as compact objects
  (``id``/``name``/``display_name``) instead of duplicating the whole catalog.

Raw protobuf payloads are excluded by default; pass ``include_raw=True`` to keep
them.  The catalog's 160k-entry string table is also excluded unless you pass
``include_strings=True``.

Examples
--------
>>> from sims4_sdk import Sims4Workspace
>>> ws = Sims4Workspace()
>>> ws.catalog.to_dict()["traits"]              # doctest: +SKIP
{'123456789': {...}, ...}
>>> ws.read_save(ws.latest_save_path()).to_json("save.json")   # doctest: +SKIP
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, Optional

from .core.dbpf import ResourceKey

__all__ = ["Serializable", "Sims4JSONEncoder", "to_dict", "to_json"]


class Serializable:
    """Mixin adding ``to_dict()`` / ``to_json()`` to a model."""

    def to_dict(self, **options: Any) -> dict[str, Any]:
        """Return a JSON-safe dictionary representation of this object."""
        return to_dict(self, **options)

    def to_json(
        self,
        path: Optional[str | Path] = None,
        *,
        indent: int | None = 2,
        ensure_ascii: bool = False,
        **options: Any,
    ) -> str:
        """Return a JSON string, optionally writing it to ``path``."""
        return to_json(
            self,
            path,
            indent=indent,
            ensure_ascii=ensure_ascii,
            **options,
        )


# ----------------------------------------------------------------------
# options and generic conversion
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _Options:
    include_raw: bool = False
    include_strings: bool = False
    include_tuning_index: bool = False


def _options(
    *,
    include_raw: bool = False,
    include_strings: bool = False,
    include_tuning_index: bool = False,
) -> _Options:
    return _Options(include_raw, include_strings, include_tuning_index)


def _jsonable(value: Any, options: _Options) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if isinstance(value, ResourceKey) or (
        isinstance(value, tuple) and hasattr(value, "_fields")
    ):
        return (
            str(value) if isinstance(value, ResourceKey) else _jsonable(list(value), options)
        )
    if isinstance(value, dict):
        return {str(key): _jsonable(item, options) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item, options) for item in value]
    if hasattr(value, "to_dict"):
        return to_dict(
            value,
            include_raw=options.include_raw,
            include_strings=options.include_strings,
            include_tuning_index=options.include_tuning_index,
        )
    if is_dataclass(value):
        return _dataclass_dict(value, options)
    return str(value)


def _dataclass_dict(obj: Any, options: _Options) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields(obj):
        if not field.repr and not options.include_raw:
            continue
        result[field.name] = _jsonable(getattr(obj, field.name), options)
    return result


def _by_id(mapping: dict[int, Any], converter, options: _Options) -> dict[str, Any]:
    return {str(key): converter(value, options) for key, value in mapping.items()}


# ----------------------------------------------------------------------
# compact references to catalog definitions
# ----------------------------------------------------------------------
def _source(value: Any) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    return {
        "package": value.package,
        "pack": value.pack,
        "is_mod": value.is_mod,
        "label": value.label,
        "path": value.path,
        "resource_key": str(value.resource_key) if value.resource_key is not None else None,
    }


def _ref(value: Any, keys: tuple[str, ...]) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    return {key: getattr(value, key, None) for key in keys}


def _trait_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name", "trait_type"))


def _preference_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name", "preference_type"))


def _aspiration_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name"))


def _aspiration_track_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name"))


def _career_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name"))


def _career_track_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name"))


def _career_level_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "title", "level", "pay_per_hour"))


def _milestone_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name"))


def _relationship_bit_ref(value: Any) -> Optional[dict[str, Any]]:
    return _ref(value, ("id", "name", "display_name"))


# ----------------------------------------------------------------------
# catalog models
# ----------------------------------------------------------------------
def _trait_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "trait_type": value.trait_type,
        "ages": list(value.ages),
        "species": list(value.species),
        "occults": list(value.occults),
        "ui_category": value.ui_category,
        "is_hidden": value.is_hidden,
        "is_internal": value.is_internal,
        "is_personality": value.is_personality,
        "icon": value.icon,
        "conflicting_trait_ids": list(value.conflicting_trait_ids),
        "source": _source(value.source),
    }


def _preference_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "preference_type": value.preference_type,
        "item": value.item,
        "ages": list(value.ages),
        "species": list(value.species),
        "is_like": value.is_like,
        "is_dislike": value.is_dislike,
        "conflicting_trait_ids": list(value.conflicting_trait_ids),
        "source": _source(value.source),
    }


def _aspiration_category_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "sort_order": value.sort_order,
        "source": _source(value.source),
    }


def _aspiration_track_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "category_id": value.category_id,
        "aspiration_ids": list(value.aspiration_ids),
        "primary_trait_id": value.primary_trait_id,
        "reward_id": value.reward_id,
        "icon": value.icon,
        "source": _source(value.source),
    }


def _aspiration_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "track_id": value.track_id,
        "category_id": value.category_id,
        "valid_ages": list(value.valid_ages),
        "objective_ids": list(value.objective_ids),
        "primary_trait_id": value.primary_trait_id,
        "icon": value.icon,
        "source": _source(value.source),
    }


def _career_track_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "level_ids": list(value.level_ids),
        "icon": value.icon,
        "source": _source(value.source),
    }


def _career_level_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "title": value.title,
        "description": value.description,
        "track_id": value.track_id,
        "level": value.level,
        "pay_per_hour": value.pay_per_hour,
        "pay_type": value.pay_type,
        "aspiration_id": value.aspiration_id,
        "promotion_reward_id": value.promotion_reward_id,
        "work_days": list(value.work_days),
        "work_start_time": value.work_start_time,
        "work_duration": value.work_duration,
        "source": _source(value.source),
    }


def _career_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "start_track_id": value.start_track_id,
        "track_ids": list(value.track_ids),
        "category": value.category,
        "source": _source(value.source),
    }


def _milestone_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "category": value.category,
        "ages": list(value.ages),
        "repeatable": value.repeatable,
        "is_primary": value.is_primary,
        "goal_id": value.goal_id,
        "icon": value.icon,
        "unlocked_text": value.unlocked_text,
        "source": _source(value.source),
    }


def _relationship_bit_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "description": value.description,
        "depth": value.depth,
        "visible": value.visible,
        "icon": value.icon,
        "triggered_track_id": value.triggered_track_id,
        "source": _source(value.source),
    }


def _track_value_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "track_id": value.track_id,
        "track_name": value.track_name,
        "value": value.value,
        "min_value": value.min_value,
        "max_value": value.max_value,
    }


def _relationship_default_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "link": value.link,
        "tracks": [_track_value_dict(item, options) for item in value.tracks],
        "bit_ids": list(value.bit_ids),
        "loot_ids": list(value.loot_ids),
    }


def _premade_relationship_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "sim_a": value.sim_a,
        "sim_b": value.sim_b,
        "sim_a_name": value.sim_a_name,
        "sim_b_name": value.sim_b_name,
        "friendship": value.friendship,
        "romance": value.romance,
        "tracks": [_track_value_dict(item, options) for item in value.tracks],
        "bit_ids": list(value.bit_ids),
        "sentiment_track_ids": list(value.sentiment_track_ids),
        "loot_id": value.loot_id,
    }


def _gender_options_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "gender": value.gender,
        "frame": value.frame,
        "clothing": value.clothing,
        "toilet_use": value.toilet_use,
        "lactation": value.lactation,
        "attracted_to": list(value.attracted_to),
        "not_attracted_to": list(value.not_attracted_to),
        "woohoo_interests": list(value.woohoo_interests),
        "not_woohoo_interests": list(value.not_woohoo_interests),
        "sexuality": value.sexuality,
        "can_impregnate": value.can_impregnate,
        "can_be_impregnated": value.can_be_impregnated,
    }


def _skill_level_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "skill_id": value.skill_id,
        "skill_name": value.skill_name,
        "level": value.level,
        "min_value": value.min_value,
        "max_value": value.max_value,
        "ideal_value": value.ideal_value,
        "value": value.value,
    }


def _catalog_dict(catalog: Any, options: _Options) -> dict[str, Any]:
    data: dict[str, Any] = {
        "traits": _by_id(catalog.traits, _trait_dict, options),
        "preferences": _by_id(catalog.preferences, _preference_dict, options),
        "aspirations": _by_id(catalog.aspirations, _aspiration_dict, options),
        "aspiration_tracks": _by_id(
            catalog.aspiration_tracks, _aspiration_track_dict, options
        ),
        "aspiration_categories": _by_id(
            catalog.aspiration_categories, _aspiration_category_dict, options
        ),
        "careers": _by_id(catalog.careers, _career_dict, options),
        "career_tracks": _by_id(catalog.career_tracks, _career_track_dict, options),
        "career_levels": _by_id(catalog.career_levels, _career_level_dict, options),
        "milestones": _by_id(catalog.milestones, _milestone_dict, options),
        "relationship_bits": _by_id(
            catalog.relationship_bits, _relationship_bit_dict, options
        ),
        "relationship_defaults": {
            key: _relationship_default_dict(value, options)
            for key, value in catalog.relationship_defaults.items()
        },
        "premade_relationships": [
            _premade_relationship_dict(item, options)
            for item in catalog.premade_relationships
        ],
        "relationship_track_ranges": _by_id(
            catalog.relationship_track_ranges, _track_value_dict, options
        ),
        "steady_bit_id": catalog.steady_bit_id,
        "engagement_bit_id": catalog.engagement_bit_id,
        "marriage_bit_id": catalog.marriage_bit_id,
        "family_trope_ids": list(catalog.family_trope_ids),
        "romance_trope_ids": list(catalog.romance_trope_ids),
        "errors": list(catalog.errors),
        "diagnostics": [_dataclass_dict(issue, options) for issue in catalog.diagnostics],
    }
    if options.include_strings:
        data["strings"] = {str(key): value for key, value in catalog.strings.items()}
    if options.include_tuning_index:
        data["tuning_names"] = {
            str(key): value for key, value in catalog.tuning_names.items()
        }
        data["tuning_classes"] = {
            str(key): value for key, value in catalog.tuning_classes.items()
        }
    return data


# ----------------------------------------------------------------------
# pre-made models
# ----------------------------------------------------------------------
def _premade_sim_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "first_name": value.first_name,
        "last_name": value.last_name,
        "full_name": value.full_name,
        "household_id": value.household_id,
        "household_name": value.household_name,
        "age": value.age,
        "gender": value.gender,
        "species": value.species,
        "occult": value.occult,
        "pronouns": value.pronouns,
        "gender_hint": value.gender_hint,
        "age_hint": value.age_hint,
        "body_blend": value.body_blend,
        "siminfo_key": str(value.siminfo_key) if value.siminfo_key else None,
        "explicit_trait_ids": list(value.explicit_trait_ids),
        "siminfo_trait_ids": list(value.siminfo_trait_ids),
        "unknown_trait_ids": list(value.unknown_trait_ids),
        "random_trait_count": value.random_trait_count,
        "traits": [_trait_ref(item) for item in value.traits],
        "personality_traits": [
            _trait_ref(item) for item in value.personality_traits
        ],
        "visible_traits": [_trait_ref(item) for item in value.visible_traits],
        "preferences": [_preference_ref(item) for item in value.preferences],
        "likes": [_preference_ref(item) for item in value.likes],
        "dislikes": [_preference_ref(item) for item in value.dislikes],
        "skills": [_skill_level_dict(item, options) for item in value.skills],
        "aspiration_id": value.aspiration_id,
        "aspiration": _aspiration_ref(value.aspiration),
        "aspiration_track_id": value.aspiration_track_id,
        "aspiration_track": _aspiration_track_ref(value.aspiration_track),
        "career_id": value.career_id,
        "career": _career_ref(value.career),
        "career_track_id": value.career_track_id,
        "career_track": _career_track_ref(value.career_track),
        "career_level_id": value.career_level_id,
        "career_level": _career_level_ref(value.career_level),
        "career_track_level": value.career_track_level,
        "career_display_level": value.career_display_level,
        "dynasty": _jsonable(value.dynasty, options),
        "pregnancy": _jsonable(value.pregnancy, options),
        "gender_options": _gender_options_dict(value.gender_options, options),
        "spouse_id": value.spouse_id,
        "spouse_name": value.spouse_name,
        "parents": list(value.parents),
        "children": list(value.children),
        "siblings": list(value.siblings),
        "extended_family": list(value.extended_family),
        "source": _source(value.source),
    }


def _household_member_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "tag": value.tag,
        "sim_template_id": value.sim_template_id,
        "sim_name": value.sim_name,
        "full_name": value.full_name,
    }


def _household_relationship_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "kind": value.kind,
        "a_tag": value.a_tag,
        "b_tag": value.b_tag,
        "family_relationship": value.family_relationship,
        "friendship": value.friendship,
        "romance": value.romance,
        "friendship_min": value.friendship_min,
        "friendship_max": value.friendship_max,
        "romance_min": value.romance_min,
        "romance_max": value.romance_max,
        "bit_ids": list(value.bit_ids),
    }


def _premade_household_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "display_name": value.display_name,
        "localized_name": value.localized_name,
        "description": value.description,
        "lot_id": value.lot_id,
        "lot_ids": list(value.lot_ids),
        "hidden": value.hidden,
        "townie_street": value.townie_street,
        "funds": value.funds,
        "member_ids": list(value.member_ids),
        "members": [
            _household_member_dict(item, options) for item in value.members
        ],
        "relationships": [
            _household_relationship_dict(item, options)
            for item in value.relationships
        ],
        "source": _source(value.source),
    }


def _premade_ancestor_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "name": value.name,
        "full_name": value.full_name,
        "gender": value.gender,
        "death_trait_id": value.death_trait_id,
        "thumbnail": value.thumbnail,
        "source": _source(value.source),
    }


def _premade_lot_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "id": value.id,
        "lot_name": value.lot_name,
        "lot_description": value.lot_description,
        "household_name": value.household_name,
        "household_description": value.household_description,
        "household_id": value.household_id,
        "lot_name_key": value.lot_name_key,
        "lot_description_key": value.lot_description_key,
        "has_household": value.has_household,
        "source": _source(value.source),
    }


def _premade_bundle_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "sims": [_premade_sim_dict(item, options) for item in value.sims],
        "households": [
            _premade_household_dict(item, options) for item in value.households
        ],
        "ancestors": [
            _premade_ancestor_dict(item, options) for item in value.ancestors
        ],
        "lots": [_premade_lot_dict(item, options) for item in value.lots],
        "premade_relationships": [
            _premade_relationship_dict(item, options)
            for item in value.premade_relationships
        ],
    }


# ----------------------------------------------------------------------
# save and Tray models
# ----------------------------------------------------------------------
def _slot_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_skill_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "skill_id": value.skill_id,
        "name": value.name,
        "tuning_class": value.tuning_class,
        "value": value.value,
        "level": value.level,
    }


def _saved_career_history_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_career_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "career_id": value.career_id,
        "track_id": value.track_id,
        "track_level": value.track_level,
        "career_name": value.career_name,
        "track_name": value.track_name,
        "level_id": value.level_id,
        "title": value.title,
        "user_display_level": value.user_display_level,
        "pay_per_hour": value.pay_per_hour,
        "pending_promotion": value.pending_promotion,
        "base_performance": value.base_performance,
        "positive_performance": value.positive_performance,
        "negative_performance": value.negative_performance,
        "career": _career_ref(value.career),
        "track": _career_track_ref(value.track),
        "level": _career_level_ref(value.level),
        "history": [
            _saved_career_history_dict(item, options) for item in value.history
        ],
    }


def _saved_relationship_track_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_relationship_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "target_id": value.target_id,
        "target_name": value.target_name,
        "value": value.value,
        "bits": list(value.bits),
        "bit_names": list(value.bit_names),
        "track_values": [
            _saved_relationship_track_dict(item, options)
            for item in value.track_values
        ],
        "last_update_time": value.last_update_time,
    }


def _saved_family_relation_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_trope_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_milestone_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "milestone_id": value.milestone_id,
        "name": value.name,
        "display_name": value.display_name,
        "state": value.state,
        "age_completed": value.age_completed,
        "new_in_ui": value.new_in_ui,
        "milestone": _milestone_ref(value.milestone),
    }


def _saved_timed_aspiration_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_statistic_dict(value: Any, options: _Options) -> dict[str, Any]:
    return _dataclass_dict(value, options)


def _saved_sim_dict(value: Any, options: _Options) -> dict[str, Any]:
    data = {
        "sim_id": value.sim_id,
        "first_name": value.first_name,
        "last_name": value.last_name,
        "full_name": value.full_name,
        "nucleus_id": value.nucleus_id,
        "household_id": value.household_id,
        "household_name": value.household_name,
        "zone_id": value.zone_id,
        "world_id": value.world_id,
        "age_raw": value.age_raw,
        "age": value.age,
        "gender_raw": value.gender_raw,
        "gender": value.gender,
        "species_raw": value.species_raw,
        "species": value.species,
        "occult_raw": value.occult_raw,
        "occult": list(value.occult),
        "pronouns": value.pronouns,
        "is_dead": value.is_dead,
        "primary_aspiration_track_id": value.primary_aspiration_track_id,
        "aspiration_track": _aspiration_track_ref(value.aspiration_track),
        "traits": [_trait_ref(item) for item in value.traits],
        "personality_traits": [
            _trait_ref(item) for item in value.personality_traits
        ],
        "visible_traits": [_trait_ref(item) for item in value.visible_traits],
        "preferences": [_preference_ref(item) for item in value.preferences],
        "likes": [_preference_ref(item) for item in value.likes],
        "dislikes": [_preference_ref(item) for item in value.dislikes],
        "unknown_trait_ids": list(value.unknown_trait_ids),
        "gender_options": _gender_options_dict(value.gender_options, options),
        "careers": [_saved_career_dict(item, options) for item in value.careers],
        "skills": [_saved_skill_dict(item, options) for item in value.skills],
        "relationships": [
            _saved_relationship_dict(item, options) for item in value.relationships
        ],
        "spouse_id": value.spouse_id,
        "spouse_name": value.spouse_name,
        "fiance_id": value.fiance_id,
        "fiance_name": value.fiance_name,
        "steady_ids": list(value.steady_ids),
        "steady_names": list(value.steady_names),
        "tropes": [_saved_trope_dict(item, options) for item in value.tropes],
        "parents": [
            _saved_family_relation_dict(item, options) for item in value.parents
        ],
        "children": [
            _saved_family_relation_dict(item, options) for item in value.children
        ],
        "siblings": [
            _saved_family_relation_dict(item, options) for item in value.siblings
        ],
        "extended_family": [
            _saved_family_relation_dict(item, options) for item in value.extended_family
        ],
        "milestones": [
            _saved_milestone_dict(item, options) for item in value.milestones
        ],
        "objective_ids": list(value.objective_ids),
        "completed_milestone_ids": list(value.completed_milestone_ids),
        "timed_aspirations": [
            _saved_timed_aspiration_dict(item, options)
            for item in value.timed_aspirations
        ],
        "pregnancy": _jsonable(value.pregnancy, options),
        "degree": _jsonable(value.degree, options),
        "death": _jsonable(value.death, options),
        "favorites": _jsonable(value.favorites, options),
        "statistics": [
            _saved_statistic_dict(item, options) for item in value.statistics
        ],
    }
    if options.include_raw:
        data["raw"] = _jsonable(value.raw, options)
    return data


def _saved_household_dict(value: Any, options: _Options) -> dict[str, Any]:
    data = {
        "household_id": value.household_id,
        "name": value.name,
        "money": value.money,
        "home_zone": value.home_zone,
        "last_played_sim_id": value.last_played_sim_id,
        "creation_time": value.creation_time,
        "last_modified_time": value.last_modified_time,
        "is_unplayed": value.is_unplayed,
        "is_player": value.is_player,
        "hidden": value.hidden,
        "premade_household_id": value.premade_household_id,
        "premade_household_template_id": value.premade_household_template_id,
        "description": value.description,
        "member_ids": list(value.member_ids),
        "members": list(value.members),
        "milestones_completed": list(value.milestones_completed),
    }
    if options.include_raw:
        data["raw"] = _jsonable(value.raw, options)
    return data


def _save_file_dict(value: Any, options: _Options) -> dict[str, Any]:
    data = {
        "path": str(value.path),
        "slot": _slot_dict(value.slot, options),
        "account": _slot_dict(value.account, options),
        "sims": _by_id(value.sims, _saved_sim_dict, options),
        "households": _by_id(value.households, _saved_household_dict, options),
        "zones": _by_id(value.zones, _slot_dict, options),
        "neighborhoods": _by_id(value.neighborhoods, _slot_dict, options),
        "artwork": {
            str(key): {"width": image.width, "height": image.height, "alpha_format": image.alpha_format}
            for key, image in value.artwork.items()
        },
        "artwork_errors": list(value.artwork_errors),
    }
    if options.include_raw:
        data["raw"] = _jsonable(value.raw, options)
        data["artwork"] = {str(key): _dataclass_dict(image, options) for key, image in value.artwork.items()}
    return data


def _tray_item_dict(value: Any, options: _Options) -> dict[str, Any]:
    data = {
        "path": str(value.path),
        "item_id": value.item_id,
        "item_type": value.item_type,
        "hash": value.hash.hex() if value.hash else None,
        "title": value.title,
        "description": value.description,
        "creator": value.creator,
        "timestamp": value.timestamp,
    }
    if options.include_raw:
        data["raw"] = _jsonable(value.raw, options)
    return data


def _tray_household_dict(value: Any, options: _Options) -> dict[str, Any]:
    data = {
        "path": str(value.path),
        "item": _tray_item_dict(value.item, options) if value.item else None,
        "family_name": value.family_name,
        "description": value.description,
        "money": value.money,
        "home_zone": value.home_zone,
        "last_played_sim_id": value.last_played_sim_id,
        "hashtag_description": value.hashtag_description,
        "sims": [_saved_sim_dict(item, options) for item in value.sims],
    }
    if options.include_raw:
        data["raw"] = _jsonable(value.raw, options)
    return data


def _tray_library_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "items": [_tray_item_dict(item, options) for item in value.items],
        "errors": list(value.errors),
        "households": [
            _tray_household_dict(item, options) for item in value.households
        ],
    }


def _static_data_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "catalog": _catalog_dict(value.catalog, options),
        "premades": _premade_bundle_dict(value.premades, options),
        "world": _world_data_dict(value.world, options) if value.world is not None else None,
    }


def _world_data_dict(value: Any, options: _Options) -> dict[str, Any]:
    return {
        "households": _by_id(value.households, _dataclass_dict, options),
        "lots": _by_id(value.lots, _dataclass_dict, options),
        "household_resources": _by_id(value.household_resources, _dataclass_dict, options),
        "lot_resources": _by_id(value.lot_resources, _dataclass_dict, options),
        "errors": list(value.errors),
        "diagnostics": [_dataclass_dict(issue, options) for issue in value.diagnostics],
    }


# ----------------------------------------------------------------------
# dispatch
# ----------------------------------------------------------------------
def to_dict(obj: Any, **options: Any) -> dict[str, Any]:
    """Convert any SDK model (or nested structure) to a JSON-safe dictionary.

    Parameters
    ----------
    obj:
        A model instance, list, or dictionary.
    include_raw:
        Keep the raw decoded protobuf payloads (default ``False``).
    include_strings:
        Include the catalog's full STBL string table (default ``False``).
    include_tuning_index:
        Include ``Catalog.tuning_names`` / ``tuning_classes`` (default ``False``).
    """
    opts = _options(**options)

    from .catalog.models import (
        Aspiration,
        AspirationCategory,
        AspirationTrack,
        Career,
        CareerLevel,
        CareerTrack,
        Catalog,
        GenderOptions,
        Milestone,
        PremadeRelationship,
        Preference,
        RelationshipBit,
        RelationshipDefault,
        RelationshipTrackValue,
        SkillLevel,
        Trait,
        TuningSource,
    )
    from .catalog.premades import (
        HouseholdMember,
        HouseholdRelationship,
        PremadeAncestor,
        PremadeBundle,
        PremadeHousehold,
        PremadeLot,
        PremadeSim,
    )
    from .catalog.static import StaticData
    from .save.models import (
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

    if isinstance(obj, StaticData):
        return _static_data_dict(obj, opts)
    if isinstance(obj, Catalog):
        return _catalog_dict(obj, opts)
    if isinstance(obj, PremadeBundle):
        return _premade_bundle_dict(obj, opts)
    if isinstance(obj, PremadeSim):
        return _premade_sim_dict(obj, opts)
    if isinstance(obj, PremadeHousehold):
        return _premade_household_dict(obj, opts)
    if isinstance(obj, PremadeAncestor):
        return _premade_ancestor_dict(obj, opts)
    if isinstance(obj, PremadeLot):
        return _premade_lot_dict(obj, opts)
    if isinstance(obj, HouseholdMember):
        return _household_member_dict(obj, opts)
    if isinstance(obj, HouseholdRelationship):
        return _household_relationship_dict(obj, opts)
    if isinstance(obj, Trait):
        return _trait_dict(obj, opts)
    if isinstance(obj, Preference):
        return _preference_dict(obj, opts)
    if isinstance(obj, AspirationTrack):
        return _aspiration_track_dict(obj, opts)
    if isinstance(obj, AspirationCategory):
        return _aspiration_category_dict(obj, opts)
    if isinstance(obj, Aspiration):
        return _aspiration_dict(obj, opts)
    if isinstance(obj, CareerTrack):
        return _career_track_dict(obj, opts)
    if isinstance(obj, CareerLevel):
        return _career_level_dict(obj, opts)
    if isinstance(obj, Career):
        return _career_dict(obj, opts)
    if isinstance(obj, Milestone):
        return _milestone_dict(obj, opts)
    if isinstance(obj, RelationshipBit):
        return _relationship_bit_dict(obj, opts)
    if isinstance(obj, RelationshipTrackValue):
        return _track_value_dict(obj, opts)
    if isinstance(obj, RelationshipDefault):
        return _relationship_default_dict(obj, opts)
    if isinstance(obj, PremadeRelationship):
        return _premade_relationship_dict(obj, opts)
    if isinstance(obj, GenderOptions):
        return _gender_options_dict(obj, opts)
    if isinstance(obj, SkillLevel):
        return _skill_level_dict(obj, opts)
    if isinstance(obj, SaveFile):
        return _save_file_dict(obj, opts)
    if isinstance(obj, SavedSim):
        return _saved_sim_dict(obj, opts)
    if isinstance(obj, SavedHousehold):
        return _saved_household_dict(obj, opts)
    if isinstance(obj, SavedCareer):
        return _saved_career_dict(obj, opts)
    if isinstance(obj, SavedCareerHistory):
        return _saved_career_history_dict(obj, opts)
    if isinstance(obj, SavedSkill):
        return _saved_skill_dict(obj, opts)
    if isinstance(obj, SavedRelationship):
        return _saved_relationship_dict(obj, opts)
    if isinstance(obj, SavedRelationshipTrack):
        return _saved_relationship_track_dict(obj, opts)
    if isinstance(obj, SavedFamilyRelation):
        return _saved_family_relation_dict(obj, opts)
    if isinstance(obj, SavedRelationshipTrope):
        return _saved_trope_dict(obj, opts)
    if isinstance(obj, SavedMilestone):
        return _saved_milestone_dict(obj, opts)
    if isinstance(obj, SavedTimedAspiration):
        return _saved_timed_aspiration_dict(obj, opts)
    if isinstance(obj, SavedStatistic):
        return _saved_statistic_dict(obj, opts)
    if isinstance(obj, TuningSource):
        return _source(obj)
    from .save.artwork import Artwork
    from .catalog.diagnostics import ExtractionIssue
    if isinstance(obj, (SaveSlot, SaveAccount, SaveZone, SaveNeighborhood, Artwork, ExtractionIssue)):
        return _dataclass_dict(obj, opts)
    if isinstance(obj, TrayLibrary):
        return _tray_library_dict(obj, opts)
    if isinstance(obj, TrayHousehold):
        return _tray_household_dict(obj, opts)
    if isinstance(obj, TrayItem):
        return _tray_item_dict(obj, opts)
    if isinstance(obj, dict):
        return _jsonable(obj, opts)
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_jsonable(item, opts) for item in obj]
    if hasattr(obj, "to_dict"):
        # Non-SDK models (for example ``ValidationReport``) bring their own
        # conversion.  Calling it here prevents a recursive round-trip through
        # ``_jsonable``.
        result = obj.to_dict()
        if isinstance(result, dict):
            return result
        raise TypeError(
            f"{type(obj).__name__}.to_dict() did not return a dictionary"
        )

    converted = _jsonable(obj, opts)
    if isinstance(converted, dict):
        return converted
    raise TypeError(
        f"cannot convert {type(obj).__name__!r} to a dictionary; "
        "pass an SDK model, list, or dict"
    )


class Sims4JSONEncoder(json.JSONEncoder):
    """``json`` encoder that understands SDK models and binary values."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, (bytes, bytearray)):
            return bytes(o).hex()
        if isinstance(o, ResourceKey):
            return str(o)
        if hasattr(o, "to_dict"):
            return o.to_dict()
        if is_dataclass(o):
            return _dataclass_dict(o, _Options())
        return super().default(o)


def to_json(
    obj: Any,
    path: Optional[str | Path] = None,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
    **options: Any,
) -> str:
    """Serialize ``obj`` to JSON, optionally writing it to ``path``.

    Returns the JSON string.  ``indent=2`` produces readable output; pass
    ``indent=None`` for the compact form.
    """
    text = json.dumps(
        to_dict(obj, **options),
        indent=indent,
        ensure_ascii=ensure_ascii,
        cls=Sims4JSONEncoder,
    )
    if path is not None:
        target = Path(path)
        if target.parent and not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return text
