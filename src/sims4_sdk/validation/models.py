"""Data models for Sims Wiki validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

__all__ = [
    "WikiRelationship",
    "WikiSim",
    "WikiCatalogEntry",
    "FieldComparison",
    "SimComparison",
    "DomainCoverage",
    "ValidationReport",
]


@dataclass
class WikiRelationship:
    name: str
    level: str = ""
    friendship: Optional[int] = None
    romance: Optional[int] = None


@dataclass
class WikiSim:
    title: str
    name: str
    sex: Optional[str] = None
    age: Optional[str] = None
    game: Optional[str] = None
    career: Optional[str] = None
    career_level: Optional[str] = None
    aspiration: Optional[str] = None
    traits: list[str] = field(default_factory=list)
    spouse: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    family: Optional[str] = None
    play: Optional[str] = None
    neighbor: Optional[str] = None
    skills: dict[str, int] = field(default_factory=dict)
    relationships: list[WikiRelationship] = field(default_factory=list)
    raw_params: dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def full_name(self) -> str:
        return self.name or self.title


@dataclass
class WikiCatalogEntry:
    name: str
    pack: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FieldComparison:
    field: str
    wiki: Any
    sdk: Any
    status: str  # match | mismatch | missing_wiki | missing_sdk | not_available
    note: Optional[str] = None


@dataclass
class SimComparison:
    name: str
    wiki_title: Optional[str] = None
    fields: list[FieldComparison] = field(default_factory=list)

    @property
    def score(self) -> float:
        checked = [field for field in self.fields if field.status != "not_available"]
        if not checked:
            return 0.0
        matched = sum(1 for field in checked if field.status == "match")
        return matched / len(checked)

    @property
    def mismatches(self) -> list[FieldComparison]:
        return [
            field
            for field in self.fields
            if field.status in ("mismatch", "missing_wiki", "missing_sdk")
        ]


@dataclass
class DomainCoverage:
    domain: str
    wiki_count: int
    sdk_count: int
    matched: list[str] = field(default_factory=list)
    missing_in_sdk: list[str] = field(default_factory=list)
    extra_in_sdk: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return len(self.matched) / self.wiki_count if self.wiki_count else 0.0


@dataclass
class ValidationReport:
    catalog: dict[str, DomainCoverage] = field(default_factory=dict)
    sims: list[SimComparison] = field(default_factory=list)
    save_label: Optional[str] = None
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        catalog_summary = {
            domain: {
                "wiki": coverage.wiki_count,
                "sdk": coverage.sdk_count,
                "matched": len(coverage.matched),
                "missing_in_sdk": len(coverage.missing_in_sdk),
                "extra_in_sdk": len(coverage.extra_in_sdk),
                "coverage": round(coverage.coverage, 4),
            }
            for domain, coverage in self.catalog.items()
        }
        sims_checked = len(self.sims)
        sims_with_mismatch = sum(1 for sim in self.sims if sim.mismatches)
        return {
            "generated_at": self.generated_at,
            "save": self.save_label,
            "catalog": catalog_summary,
            "sims_checked": sims_checked,
            "sims_with_mismatch": sims_with_mismatch,
            "metadata": self.metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary(),
            "catalog": {
                domain: {
                    "wiki_count": coverage.wiki_count,
                    "sdk_count": coverage.sdk_count,
                    "matched": coverage.matched,
                    "missing_in_sdk": coverage.missing_in_sdk,
                    "extra_in_sdk": coverage.extra_in_sdk,
                    "coverage": coverage.coverage,
                }
                for domain, coverage in self.catalog.items()
            },
            "sims": [
                {
                    "name": sim.name,
                    "wiki_title": sim.wiki_title,
                    "score": sim.score,
                    "fields": [
                        {
                            "field": field.field,
                            "wiki": field.wiki,
                            "sdk": field.sdk,
                            "status": field.status,
                            "note": field.note,
                        }
                        for field in sim.fields
                    ],
                }
                for sim in self.sims
            ],
        }

    def to_markdown(self) -> str:
        lines = ["# Sims Wiki validation report", ""]
        lines.append(f"Generated: `{self.generated_at}`")
        if self.save_label:
            lines.append(f"Save: `{self.save_label}`")
        lines.append("")

        lines.append("## Catalog coverage")
        lines.append("")
        lines.append("| Domain | Wiki | SDK | Matched | Missing in SDK | SDK-only | Coverage |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for domain, coverage in sorted(self.catalog.items()):
            lines.append(
                f"| {domain} | {coverage.wiki_count} | {coverage.sdk_count} | "
                f"{len(coverage.matched)} | {len(coverage.missing_in_sdk)} | "
                f"{len(coverage.extra_in_sdk)} | {coverage.coverage:.1%} |"
            )
        lines.append("")
        lines.append(
            "> SDK-only entries are informational; they include hidden/internal "
            "tuning that the wiki does not list as player-facing content."
        )
        lines.append("")

        for domain, coverage in sorted(self.catalog.items()):
            if coverage.missing_in_sdk:
                lines.append(f"### {domain}: missing in SDK")
                lines.append("")
                for name in coverage.missing_in_sdk[:100]:
                    lines.append(f"- {name}")
                lines.append("")

        if self.sims:
            lines.append("## Sim comparisons")
            lines.append("")
            lines.append("| Sim | Score | Mismatches |")
            lines.append("| --- | ---: | --- |")
            for sim in self.sims:
                mismatch_text = ", ".join(field.field for field in sim.mismatches) or "-"
                lines.append(f"| {sim.name} | {sim.score:.0%} | {mismatch_text} |")
            lines.append("")

            for sim in self.sims:
                if not sim.mismatches:
                    continue
                lines.append(f"### {sim.name}")
                lines.append("")
                lines.append("| Field | Wiki | SDK | Status |")
                lines.append("| --- | --- | --- | --- |")
                for field in sim.mismatches:
                    wiki = str(field.wiki).replace("|", "\\|")
                    sdk = str(field.sdk).replace("|", "\\|")
                    lines.append(f"| {field.field} | {wiki} | {sdk} | {field.status} |")
                lines.append("")

        return "\n".join(lines)
