"""High-level orchestration for Sims Wiki validation."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from ..catalog.models import Catalog
from ..catalog.static import StaticData
from ..save.models import SaveFile
from .models import DomainCoverage, SimComparison, ValidationReport, WikiCatalogEntry, WikiSim
from .normalize import normalize, normalize_sim_name
from .parse import (
    extract_premade_links,
    parse_catalog_aspirations,
    parse_catalog_careers,
    parse_catalog_likes,
    parse_catalog_milestones,
    parse_catalog_traits,
    parse_sim,
)
from .reconcile import build_report, compare_catalog, compare_sims
from .wiki_client import WikiClient

__all__ = [
    "CATALOG_PAGES",
    "fetch_catalog_data",
    "fetch_premade_sims",
    "catalog_coverage",
    "validate_premades",
    "validate_save",
    "run_validation",
]

CATALOG_PAGES = {
    "traits": "Trait (The Sims 4)",
    "aspirations": "Aspiration (The Sims 4)",
    "careers": "Career tracks",
    "milestones": "Milestone",
    "preferences": "Likes and dislikes",
}

_NON_SIM_PREFIXES = (
    "the sims",
    "category:",
    "file:",
    "image:",
    "template:",
    "help:",
    "gallery",
    "create a sim",
    "world",
    "neighborhood",
    "townie",
    "lot",
    "family",
    "household",
    "content pack",
    "list of",
    "patch",
    "pack",
    "expansion",
    "stuff pack",
    "game pack",
    "kit",
    "free content",
    "store",
    "trait",
    "aspiration",
    "career",
    "milestone",
    "likes and dislikes",
    "relationship",
    "skill",
    "holiday",
    "event",
    "challenge",
    "walkthrough",
)


def fetch_catalog_data(client: WikiClient) -> dict[str, list[WikiCatalogEntry]]:
    """Fetch and parse the wiki's TS4 catalog pages."""
    texts = client.fetch_pages(CATALOG_PAGES.values())
    by_title = {
        title: texts.get(title, "") for title in CATALOG_PAGES.values()
    }
    return {
        "traits": parse_catalog_traits(by_title[CATALOG_PAGES["traits"]]),
        "aspirations": parse_catalog_aspirations(by_title[CATALOG_PAGES["aspirations"]]),
        "careers": parse_catalog_careers(by_title[CATALOG_PAGES["careers"]]),
        "milestones": parse_catalog_milestones(by_title[CATALOG_PAGES["milestones"]]),
        "preferences": parse_catalog_likes(by_title[CATALOG_PAGES["preferences"]]),
    }


def fetch_premade_sims(client: WikiClient, *, limit: int = 100) -> list[WikiSim]:
    """Fetch pre-made Sim pages linked from ``Pre-made (The Sims 4)``."""
    page = client.fetch_page("Pre-made (The Sims 4)") or ""
    links = extract_premade_links(page, limit=max(limit * 10, 500))
    filtered = [
        title
        for title in links
        if not title.casefold().startswith(_NON_SIM_PREFIXES)
    ]

    sims: list[WikiSim] = []
    for start in range(0, len(filtered), 50):
        batch = filtered[start : start + 50]
        texts = client.fetch_pages(batch)
        for title, text in texts.items():
            sim = parse_sim(text, title)
            if sim is not None:
                sims.append(sim)
                if len(sims) >= limit:
                    return sims[:limit]
    return sims[:limit]


def catalog_coverage(
    catalog: Catalog,
    wiki_catalog: dict[str, list[WikiCatalogEntry]],
) -> dict[str, DomainCoverage]:
    return {
        "traits": compare_catalog(
            "traits",
            wiki_catalog.get("traits", []),
            _trait_names(catalog),
        ),
        "preferences": compare_catalog(
            "preferences",
            wiki_catalog.get("preferences", []),
            _preference_names(catalog),
        ),
        "aspirations": compare_catalog(
            "aspirations",
            wiki_catalog.get("aspirations", []),
            _aspiration_names(catalog),
        ),
        "careers": compare_catalog(
            "careers",
            wiki_catalog.get("careers", []),
            _career_names(catalog),
        ),
        "milestones": compare_catalog(
            "milestones",
            wiki_catalog.get("milestones", []),
            _milestone_names(catalog),
        ),
    }


def validate_premades(static_data: StaticData, wiki_sims: list[WikiSim]) -> list[SimComparison]:
    return compare_sims(static_data.premades.sims, wiki_sims)


def validate_save(save: SaveFile, wiki_sims: list[WikiSim]) -> list[SimComparison]:
    return compare_sims(save.sims.values(), wiki_sims, include_missing=False)


def run_validation(
    *,
    static_data: StaticData,
    client: WikiClient,
    sim_limit: int = 100,
    save: Optional[SaveFile] = None,
    catalog_only: bool = False,
) -> ValidationReport:
    wiki_catalog = fetch_catalog_data(client)
    coverage = catalog_coverage(static_data.catalog, wiki_catalog)

    comparisons: list[SimComparison] = []
    if not catalog_only:
        wiki_sims = fetch_premade_sims(client, limit=sim_limit)
        if save is not None:
            comparisons = validate_save(save, wiki_sims)
        else:
            comparisons = validate_premades(static_data, wiki_sims)

    return build_report(
        catalog=coverage,
        sims=comparisons,
        save_label=save.slot.slot_name if save else None,
        metadata={
            "wiki_pages": dict(CATALOG_PAGES),
            "sim_limit": sim_limit,
            "catalog_only": catalog_only,
        },
    )


# ----------------------------------------------------------------------
# SDK name lists
# ----------------------------------------------------------------------
def _trait_names(catalog: Catalog) -> list[str]:
    names: list[str] = []
    internal = {
        "HIDDEN",
        "GENDER_OPTIONS",
        "WALKSTYLE",
        "TAILSTYLE",
        "SIM_PHONE",
        "AGENT",
        "SPECIES",
        "AGE",
    }
    for trait in catalog.traits.values():
        if trait.is_hidden or trait.trait_type in internal:
            continue
        names.append(trait.display_name)
        names.append(trait.name.removeprefix("trait_"))
    return names


def _preference_names(catalog: Catalog) -> list[str]:
    names: list[str] = []
    for preference in catalog.preferences.values():
        if not preference.is_like and not preference.is_dislike:
            continue
        names.append(preference.display_name)
        names.append(preference.name.removeprefix("trait_"))
        if preference.item:
            names.append(preference.item)
    return names


def _aspiration_names(catalog: Catalog) -> list[str]:
    names: list[str] = []
    for aspiration in catalog.aspirations.values():
        names.append(aspiration.display_name)
        names.append(re.sub(r"\{[^}]*\}", "", aspiration.display_name or "").strip())
        names.append(aspiration.name.removeprefix("aspiration_"))
    for track in catalog.aspiration_tracks.values():
        names.append(track.display_name)
    return names


def _career_names(catalog: Catalog) -> list[str]:
    names: list[str] = []
    for career in catalog.careers.values():
        names.append(career.name.removeprefix("career_"))
    for track in catalog.career_tracks.values():
        names.append(track.display_name)
    return names


def _milestone_names(catalog: Catalog) -> list[str]:
    names: list[str] = []
    for milestone in catalog.milestones.values():
        names.append(milestone.display_name)
        names.append(
            milestone.name.removeprefix("lifeMilestone_").removeprefix("milestone_")
        )
    return names
