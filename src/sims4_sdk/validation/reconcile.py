"""Compare SDK data with parsed Sims Wiki data."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .models import (
    DomainCoverage,
    FieldComparison,
    SimComparison,
    ValidationReport,
    WikiCatalogEntry,
    WikiSim,
)
from .normalize import (
    age_name,
    gender_name,
    names_match,
    normalize,
    normalize_sim_name,
    normalize_skill,
)

__all__ = [
    "compare_sim",
    "compare_sims",
    "compare_catalog",
    "build_report",
]


# ----------------------------------------------------------------------
# Sim comparison
# ----------------------------------------------------------------------
def compare_sim(sdk_sim: Any, wiki_sim: WikiSim) -> SimComparison:
    fields: list[FieldComparison] = []

    fields.append(
        _field(
            "name",
            wiki_sim.full_name,
            _sdk_name(sdk_sim),
            bool(names_match(wiki_sim.full_name, _sdk_name(sdk_sim))),
        )
    )

    wiki_age = age_name(wiki_sim.age)
    sdk_age = _sdk_age(sdk_sim)
    fields.append(_field("age", wiki_age, sdk_age, _compare_scalar(wiki_age, sdk_age)))

    wiki_gender = gender_name(wiki_sim.sex)
    sdk_gender = _sdk_gender(sdk_sim)
    fields.append(
        _field("gender", wiki_gender, sdk_gender, _compare_scalar(wiki_gender, sdk_gender))
    )

    fields.append(
        _compare_name_sets("traits", wiki_sim.traits, _sdk_traits(sdk_sim))
    )

    sdk_aspiration = _sdk_aspiration(sdk_sim)
    fields.append(
        _compare_name_sets(
            "aspiration",
            [wiki_sim.aspiration] if wiki_sim.aspiration else [],
            [sdk_aspiration] if sdk_aspiration else [],
        )
    )

    wiki_career = _join_filtered(wiki_sim.career, wiki_sim.career_level)
    sdk_career = _sdk_career(sdk_sim)
    if wiki_career and sdk_career:
        matched = names_match(wiki_sim.career, sdk_career) or names_match(
            wiki_sim.career_level or "", sdk_career
        )
        status = "match" if matched else "mismatch"
    elif wiki_career and not sdk_career:
        status = "missing_sdk"
    elif sdk_career and not wiki_career:
        status = "not_available"
    else:
        status = "not_available"
    fields.append(FieldComparison("career", wiki_career, sdk_career, status))

    fields.append(_compare_name_sets("spouse", wiki_sim.spouse, _sdk_spouse(sdk_sim)))
    fields.append(_compare_name_sets("children", wiki_sim.children, _sdk_children(sdk_sim)))
    fields.append(_compare_name_sets("parents", wiki_sim.parents, _sdk_parents(sdk_sim)))

    wiki_skills = list(wiki_sim.skills)
    sdk_skills = _sdk_skills(sdk_sim)
    fields.append(_compare_subset("skills", wiki_skills, sdk_skills, normalizer=normalize_skill))

    relationships = _sdk_relationships(sdk_sim)
    if not relationships:
        fields.append(
            FieldComparison(
                "relationships",
                [rel.name for rel in wiki_sim.relationships],
                [],
                "not_available",
                "SDK has no relationship tracker values for this Sim (legacy save chunk?)",
            )
        )
    else:
        fields.append(
            _compare_name_sets(
                "relationships",
                [rel.name for rel in wiki_sim.relationships],
                [relationship.target_name or str(relationship.target_id) for relationship in relationships],
            )
        )

    return SimComparison(name=wiki_sim.full_name, wiki_title=wiki_sim.title, fields=fields)


def compare_sims(
    sdk_sims: Iterable[Any],
    wiki_sims: Iterable[WikiSim],
    *,
    include_missing: bool = True,
) -> list[SimComparison]:
    by_name = {normalize_sim_name(_sdk_name(sim)): sim for sim in sdk_sims}
    comparisons: list[SimComparison] = []
    for wiki_sim in wiki_sims:
        sdk_sim = by_name.get(normalize_sim_name(wiki_sim.full_name))
        if sdk_sim is None:
            if not include_missing:
                continue
            comparisons.append(
                SimComparison(
                    name=wiki_sim.full_name,
                    wiki_title=wiki_sim.title,
                    fields=[
                        FieldComparison(
                            "name",
                            wiki_sim.full_name,
                            None,
                            "missing_sdk",
                            "No matching SDK Sim",
                        )
                    ],
                )
            )
        else:
            comparisons.append(compare_sim(sdk_sim, wiki_sim))
    return comparisons


# ----------------------------------------------------------------------
# Catalog comparison
# ----------------------------------------------------------------------
def compare_catalog(
    domain: str,
    wiki_entries: list[WikiCatalogEntry],
    sdk_names: Iterable[str],
) -> DomainCoverage:
    candidates = [name for name in dict.fromkeys(sdk_names) if normalize(name)]
    matched: list[str] = []
    missing: list[str] = []
    used: set[str] = set()

    for entry in wiki_entries:
        found = None
        min_length = 3 if domain == "preferences" else 4
        threshold = 0.85 if domain == "preferences" else 0.9
        for candidate in candidates:
            if names_match(
                entry.name,
                candidate,
                min_length=min_length,
                fuzzy_threshold=threshold,
            ):
                found = candidate
                break
        if found is None:
            missing.append(entry.name)
        else:
            matched.append(entry.name)
            used.add(found)

    extra = [name for name in candidates if name not in used]
    return DomainCoverage(
        domain=domain,
        wiki_count=len(wiki_entries),
        sdk_count=len(candidates),
        matched=matched,
        missing_in_sdk=missing,
        extra_in_sdk=extra,
    )


def build_report(
    *,
    catalog: dict[str, DomainCoverage] | None = None,
    sims: list[SimComparison] | None = None,
    save_label: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> ValidationReport:
    return ValidationReport(
        catalog=catalog or {},
        sims=sims or [],
        save_label=save_label,
        metadata=metadata or {},
    )


# ----------------------------------------------------------------------
# SDK adapters
# ----------------------------------------------------------------------
def _sdk_name(sim: Any) -> str:
    return getattr(sim, "full_name", "") or getattr(sim, "name", "")


def _sdk_age(sim: Any) -> Optional[str]:
    value = getattr(sim, "age", None)
    return value.upper() if isinstance(value, str) else value


def _sdk_gender(sim: Any) -> Optional[str]:
    value = getattr(sim, "gender", None)
    return value.upper() if isinstance(value, str) else value


def _sdk_traits(sim: Any) -> list[str]:
    traits = getattr(sim, "visible_traits", None)
    if traits is None:
        traits = getattr(sim, "traits", [])
    return [getattr(trait, "display_name", None) or getattr(trait, "name", "") for trait in traits]


def _sdk_aspiration(sim: Any) -> Optional[str]:
    aspiration = getattr(sim, "aspiration", None)
    if aspiration is not None:
        return getattr(aspiration, "display_name", None) or getattr(aspiration, "name", None)
    track = getattr(sim, "aspiration_track", None)
    if track is not None:
        return getattr(track, "display_name", None) or getattr(track, "name", None)
    return None


def _sdk_career(sim: Any) -> Optional[str]:
    career = getattr(sim, "career", None)
    if career is not None:
        title = getattr(career, "title", None)
        track = getattr(career, "track_name", None)
        career_name = getattr(career, "career_name", None)
        text = _join_filtered(track, title) or career_name
        if text:
            return text
    # Prefer an explicit career level over the (broader) track name, so tuning
    # Sims that pin a level keep comparing against the same value as before.
    level = getattr(sim, "career_level", None)
    if level is not None:
        text = getattr(level, "title", None) or getattr(level, "name", None)
        if text:
            return text
    career_track = getattr(sim, "career_track", None)
    if career_track is not None:
        return getattr(career_track, "display_name", None) or getattr(
            career_track, "name", None
        )
    return None


def _sdk_spouse(sim: Any) -> list[str]:
    name = getattr(sim, "spouse_name", None)
    return [name] if name else []


def _sdk_children(sim: Any) -> list[str]:
    return _relation_names(getattr(sim, "children", []))


def _sdk_parents(sim: Any) -> list[str]:
    return _relation_names(getattr(sim, "parents", []))


def _relation_names(relations: Any) -> list[str]:
    """Accept both saved relations (objects) and static name lists."""
    names: list[str] = []
    for relation in relations or []:
        if isinstance(relation, str):
            name = relation
        else:
            name = getattr(relation, "name", None)
        if name:
            names.append(name)
    return names


def _sdk_skills(sim: Any) -> list[str]:
    names = []
    for skill in getattr(sim, "skills", []) or []:
        name = getattr(skill, "name", None) or getattr(skill, "skill_name", None)
        if name:
            names.append(name)
    return names


def _sdk_relationships(sim: Any) -> list[Any]:
    return list(getattr(sim, "relationships", []) or [])


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _field(name: str, wiki: Any, sdk: Any, matched: bool) -> FieldComparison:
    if matched:
        return FieldComparison(name, wiki, sdk, "match")
    if wiki in (None, "", []) and sdk not in (None, "", []):
        return FieldComparison(name, wiki, sdk, "missing_wiki")
    if sdk in (None, "", []) and wiki not in (None, "", []):
        return FieldComparison(name, wiki, sdk, "missing_sdk")
    return FieldComparison(name, wiki, sdk, "mismatch")


def _compare_scalar(wiki: Any, sdk: Any) -> bool:
    return normalize(str(wiki)) == normalize(str(sdk)) if wiki and sdk else False


def _compare_name_sets(
    name: str,
    wiki_names: Iterable[str],
    sdk_names: Iterable[str],
    *,
    normalizer=normalize,
) -> FieldComparison:
    wiki_list = [value for value in wiki_names if value]
    sdk_list = [value for value in sdk_names if value]
    wiki_keys = {normalizer(value) for value in wiki_list}
    sdk_keys = {normalizer(value) for value in sdk_list}
    wiki_keys.discard("")
    sdk_keys.discard("")

    if not wiki_keys and not sdk_keys:
        return FieldComparison(name, wiki_list, sdk_list, "not_available")
    if wiki_keys == sdk_keys:
        return FieldComparison(name, wiki_list, sdk_list, "match")

    wiki_only = wiki_keys - sdk_keys
    sdk_only = sdk_keys - wiki_keys
    if wiki_only and not sdk_only:
        status = "missing_sdk"
    elif sdk_only and not wiki_only:
        status = "missing_wiki"
    else:
        status = "mismatch"
    return FieldComparison(
        name,
        [value for value in wiki_list if normalizer(value) in wiki_only] or wiki_list,
        [value for value in sdk_list if normalizer(value) in sdk_only] or sdk_list,
        status,
    )


def _compare_subset(
    name: str,
    wiki_names: Iterable[str],
    sdk_names: Iterable[str],
    *,
    normalizer=normalize,
) -> FieldComparison:
    """Compare only the wiki values; SDK extras are not errors."""
    wiki_list = [value for value in wiki_names if value]
    sdk_list = [value for value in sdk_names if value]
    wiki_keys = {normalizer(value) for value in wiki_list}
    sdk_keys = {normalizer(value) for value in sdk_list}
    wiki_keys.discard("")
    sdk_keys.discard("")
    if not wiki_keys:
        return FieldComparison(name, wiki_list, sdk_list, "not_available")
    missing = wiki_keys - sdk_keys
    if not missing:
        return FieldComparison(name, wiki_list, sdk_list, "match")
    return FieldComparison(
        name,
        [value for value in wiki_list if normalizer(value) in missing],
        sdk_list,
        "missing_sdk",
    )


def _join_filtered(*values: Optional[str]) -> Optional[str]:
    parts = [value for value in values if value]
    return " / ".join(parts) if parts else None
