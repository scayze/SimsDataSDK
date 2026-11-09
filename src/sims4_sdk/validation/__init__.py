"""Sims Wiki validation: fetch, parse, and reconcile."""

from .models import (
    DomainCoverage,
    FieldComparison,
    SimComparison,
    ValidationReport,
    WikiCatalogEntry,
    WikiRelationship,
    WikiSim,
)
from .normalize import (
    age_name,
    clean_text,
    gender_name,
    names_match,
    normalize,
    normalize_sim_name,
    normalize_skill,
)
from .parse import (
    extract_premade_links,
    parse_catalog_aspirations,
    parse_catalog_careers,
    parse_catalog_likes,
    parse_catalog_milestones,
    parse_catalog_traits,
    parse_sim,
    parse_sims,
    table_rows,
)
from .reconcile import build_report, compare_catalog, compare_sim, compare_sims
from .validator import (
    CATALOG_PAGES,
    catalog_coverage,
    fetch_catalog_data,
    fetch_premade_sims,
    run_validation,
    validate_premades,
    validate_save,
)
from .wiki_client import WikiClient, WikiError

__all__ = [
    # client
    "WikiClient",
    "WikiError",
    # models
    "WikiSim",
    "WikiRelationship",
    "WikiCatalogEntry",
    "FieldComparison",
    "SimComparison",
    "DomainCoverage",
    "ValidationReport",
    # parsing
    "parse_sim",
    "parse_sims",
    "parse_catalog_traits",
    "parse_catalog_aspirations",
    "parse_catalog_careers",
    "parse_catalog_milestones",
    "parse_catalog_likes",
    "extract_premade_links",
    "table_rows",
    # normalization
    "clean_text",
    "normalize",
    "normalize_sim_name",
    "normalize_skill",
    "age_name",
    "gender_name",
    "names_match",
    # reconciliation
    "compare_sim",
    "compare_sims",
    "compare_catalog",
    "build_report",
    # orchestration
    "CATALOG_PAGES",
    "fetch_catalog_data",
    "fetch_premade_sims",
    "catalog_coverage",
    "validate_premades",
    "validate_save",
    "run_validation",
]
