"""Wikitext parsers for Sims Wiki pages."""

from __future__ import annotations

import re
from typing import Iterable, Optional

import mwparserfromhell

from .models import WikiCatalogEntry, WikiRelationship, WikiSim
from .normalize import clean_text, normalize, normalize_sim_name

__all__ = [
    "parse_sim",
    "parse_sims",
    "parse_catalog_traits",
    "parse_catalog_aspirations",
    "parse_catalog_careers",
    "parse_catalog_milestones",
    "parse_catalog_likes",
    "extract_premade_links",
    "table_rows",
]

_HEADER_CELLS = {
    "icon",
    "trait",
    "description",
    "pack",
    "career",
    "skills focus",
    "associated skills",
    "associated degree",
    "hs diploma or ged required",
    "career type",
    "levels",
    "chance card movement",
    "ep",
    "aspiration",
    "milestones and requirements",
    "reward trait",
    "milestone",
    "age",
    "activity",
    "color",
    "music genre",
    "décor style",
    "decor style",
    "fashion type",
    "characteristic",
    "quest type",
    "availability",
    "name",
}
_FILE_PREFIXES = ("file:", "image:", "category:", "template:", "help:", "media:")
_ATTRIBUTE_PATTERN = re.compile(
    r'^(?:(?:width|height|class|style|rowspan|colspan|align|valign|scope|id|lang|title)\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^|]*?)\s*)+\|'
)


# ----------------------------------------------------------------------
# generic helpers
# ----------------------------------------------------------------------
def _code(value: str):
    return mwparserfromhell.parse(value or "")


def _links(value: str, *, exclude_files: bool = True) -> list[str]:
    names: list[str] = []
    for link in _code(value).filter_wikilinks():
        target = str(link.title).strip()
        if not target:
            continue
        if exclude_files and target.casefold().startswith(_FILE_PREFIXES):
            continue
        text = clean_text(str(link.text)) if link.text else clean_text(target)
        text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
        if text:
            names.append(text)
    return names


def _first_name(value: str) -> str:
    links = _links(value)
    if links:
        return links[0]
    return clean_text(value)


def _templates(value: str, names: set[str]):
    wanted = {name.casefold().replace("_", "").replace(" ", "") for name in names}
    for template in _code(value).filter_templates(recursive=True):
        key = str(template.name).strip().casefold().replace("_", "").replace(" ", "")
        if key in wanted:
            yield template


def _param(template, name: str) -> Optional[str]:
    if not template.has(name):
        return None
    value = str(template.get(name).value).strip()
    return value or None


def _pack_from_cell(value: str) -> Optional[str]:
    for template in _templates(value, {"TS4icon", "TS4Icon", "Icon"}):
        if template.params:
            pack = clean_text(str(template.params[0].value))
            if pack:
                return pack
    match = re.search(r"link=([^|\]]+)", value)
    if match:
        return clean_text(match.group(1)) or None
    text = clean_text(value)
    return text or None


def _rows_from_table(table) -> list[list[str]]:
    rows: list[list[str]] = []
    current: list[str] = []
    for line in str(table.contents).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|-"):
            if current:
                rows.append(current)
                current = []
            continue
        if stripped.startswith("|+"):
            continue
        if stripped.startswith("|") or stripped.startswith("!"):
            current.extend(_split_cells(stripped))
            continue
        if current:
            current[-1] = f"{current[-1]}\n{stripped}".strip()
    if current:
        rows.append(current)
    return rows


def _split_cells(line: str) -> list[str]:
    line = line[1:]
    parts = re.split(r"\|\||!!", line)
    cells = []
    for part in parts:
        part = part.strip()
        match = _ATTRIBUTE_PATTERN.match(part)
        if match:
            part = part[match.end() :]
        cells.append(part.strip())
    return cells


def table_rows(table) -> list[list[str]]:
    return _rows_from_table(table)


def _tables(text: str):
    code = mwparserfromhell.parse(text)
    return [
        tag
        for tag in code.filter_tags(recursive=True)
        if str(tag.tag).strip().casefold() == "table"
    ]


# ----------------------------------------------------------------------
# Sim pages
# ----------------------------------------------------------------------
def parse_sim(text: str, title: str, *, prefer_game: str = "The Sims 4") -> Optional[WikiSim]:
    sims = parse_sims(text, title)
    if not sims:
        return None
    preferred = normalize(prefer_game)
    chosen = next((sim for sim in sims if sim.game and normalize(sim.game) == preferred), sims[0])
    skills, relationships = _parse_simology(text)
    if not chosen.skills:
        chosen.skills = skills
    if not chosen.relationships:
        chosen.relationships = relationships
    return chosen


def parse_sims(text: str, title: str) -> list[WikiSim]:
    code = mwparserfromhell.parse(text)
    infoboxes = [
        template
        for template in code.filter_templates(recursive=True)
        if str(template.name).strip().casefold().replace("_", "").replace(" ", "")
        in ("infoboxsim4", "infoboxsimfour", "sim4")
    ]
    return [_parse_infobox(template, title) for template in infoboxes]


def _parse_infobox(template, title: str) -> WikiSim:
    params = {
        str(param.name).strip(): str(param.value).strip()
        for param in template.params
        if param.name is not None
    }

    def value(name: str) -> Optional[str]:
        raw = params.get(name)
        if raw is None:
            for key, candidate in params.items():
                if key.casefold() == name.casefold():
                    raw = candidate
                    break
        return raw

    name = clean_text(value("name")) or clean_text(title)

    traits: list[str] = []
    for key, raw in params.items():
        if re.fullmatch(r"trait\d*", key.strip(), re.IGNORECASE):
            cleaned = _first_name(raw)
            if cleaned and normalize(cleaned) not in {normalize(t) for t in traits}:
                traits.append(cleaned)

    skills: dict[str, int] = {}
    for skill_template in _templates(text_of(template), {"SkillTable", "SkillTable2", "SkillTable3", "SkillTable4"}):
        for param in skill_template.params:
            key = clean_text(str(param.name))
            raw_value = clean_text(str(param.value))
            if not key or not raw_value:
                continue
            try:
                skills[key] = int(raw_value)
            except ValueError:
                continue

    relationships: list[WikiRelationship] = []
    for rel_template in _templates(text_of(template), {"RelationshipSims4", "RelationshipSims 4"}):
        target = _first_name(_param(rel_template, "name") or "")
        if not target:
            continue
        relationships.append(
            WikiRelationship(
                name=target,
                level=clean_text(_param(rel_template, "level") or ""),
                friendship=_int(_param(rel_template, "relnumber")),
                romance=_int(_param(rel_template, "romnumber")),
            )
        )

    spouse = _names_from_relative(
        _param(template, "spouse") or "",
        relation_filter={"spouse", "husband", "wife", "married"},
    )
    children = _names_from_relative(_param(template, "child") or "") + _names_from_relative(
        _param(template, "children") or ""
    )
    parents = _names_from_relative(_param(template, "parents") or "")

    return WikiSim(
        title=title,
        name=name,
        sex=clean_text(value("sex")) or None,
        age=clean_text(value("age")) or None,
        game=clean_text(value("game")) or None,
        career=clean_text(value("career")) or None,
        career_level=clean_text(value("careerlevel")) or None,
        aspiration=clean_text(value("asp")) or None,
        traits=traits,
        spouse=spouse,
        children=children,
        parents=parents,
        family=clean_text(value("family")) or None,
        play=clean_text(value("play")) or None,
        neighbor=clean_text(value("neighbor")) or None,
        skills=skills,
        relationships=relationships,
        raw_params=params,
    )


def text_of(template) -> str:
    """Stringify a template for nested template inspection."""
    return str(template)


def _parse_simology(text: str) -> tuple[dict[str, int], list[WikiRelationship]]:
    skills: dict[str, int] = {}
    skill_tables = list(_templates(text, {"SkillTable3", "SkillTable4"}))
    if skill_tables:
        for param in skill_tables[0].params:
            key = clean_text(str(param.name))
            raw_value = clean_text(str(param.value))
            if not key or not raw_value:
                continue
            try:
                skills[key] = int(raw_value)
            except ValueError:
                continue

    relationships: list[WikiRelationship] = []
    relationship_tables = list(_templates(text, {"RelationshipTableSims4"}))
    relationship_templates = (
        list(_templates(str(relationship_tables[0]), {"RelationshipSims4"}))
        if relationship_tables
        else list(_templates(text, {"RelationshipSims4", "RelationshipSims 4"}))
    )
    for rel_template in relationship_templates:
        target = _first_name(_param(rel_template, "name") or "")
        if not target:
            continue
        relationships.append(
            WikiRelationship(
                name=target,
                level=clean_text(_param(rel_template, "level") or ""),
                friendship=_int(_param(rel_template, "relnumber")),
                romance=_int(_param(rel_template, "romnumber")),
            )
        )
    return skills, relationships


def _names_from_relative(
    value: str,
    *,
    relation_filter: Optional[set[str]] = None,
) -> list[str]:
    names: list[str] = []
    templates = list(_templates(value, {"Spouse", "Relative", "Child", "Parent"}))
    for template in templates:
        params = list(template.params)
        # Relative/Spouse pairs: name, relation, name, relation...
        for index, param in enumerate(params):
            if index % 2:
                continue
            relation = clean_text(str(params[index + 1].value)) if index + 1 < len(params) else ""
            if relation_filter is not None:
                relation_key = relation.casefold()
                if not any(word in relation_key for word in relation_filter):
                    continue
            raw_name = str(param.value)
            candidates = _links(raw_name) or [_first_name(raw_name)]
            for name in candidates:
                if name and normalize(name) not in {normalize(existing) for existing in names}:
                    names.append(name)
    if not templates:
        for name in _links(value):
            if normalize(name) not in {normalize(existing) for existing in names}:
                names.append(name)
    return names


def _int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = re.search(r"-?\d+", clean_text(value))
    return int(match.group(0)) if match else None


# ----------------------------------------------------------------------
# catalog pages
# ----------------------------------------------------------------------
def parse_catalog_traits(text: str) -> list[WikiCatalogEntry]:
    entries: list[WikiCatalogEntry] = []
    seen: set[str] = set()
    for table in _tables(text):
        for row in _rows_from_table(table):
            if len(row) < 2:
                continue
            name = _first_name(row[1])
            key = normalize(name)
            if not key or key in seen or key in {normalize(h) for h in _HEADER_CELLS}:
                continue
            if key.startswith("patch"):
                continue
            seen.add(key)
            entries.append(
                WikiCatalogEntry(
                    name=name,
                    description=clean_text(row[2]) if len(row) > 2 else None,
                    pack=_pack_from_cell(row[3]) if len(row) > 3 else None,
                    category="trait",
                )
            )
    return entries


def parse_catalog_aspirations(text: str) -> list[WikiCatalogEntry]:
    entries: list[WikiCatalogEntry] = []
    seen: set[str] = set()
    for table in _tables(text):
        for row in _rows_from_table(table):
            if not row or not clean_text(row[0]):
                continue
            first = row[0]
            first_text = clean_text(first)
            # Aspiration rows carry an icon and a " - description" tail.
            # Milestone sub-rows are just bold names plus requirement bullets.
            if "[[File:" not in first and " - " not in first_text:
                continue
            bold = re.search(r"'''+(.+?)'''+", first)
            if bold:
                name = clean_text(bold.group(1))
            else:
                links = _links(first)
                name = links[0] if links else first_text.split(" - ")[0].strip('"\'')
            key = normalize(name)
            if not key or key in seen or key in {normalize(h) for h in _HEADER_CELLS}:
                continue
            if name.casefold() in ("aspiration", "milestones and requirements"):
                continue
            seen.add(key)
            entries.append(
                WikiCatalogEntry(
                    name=name,
                    description=first_text,
                    pack=_pack_from_cell(row[-1]) if row else None,
                    category="aspiration",
                )
            )
    return entries


def parse_catalog_careers(text: str) -> list[WikiCatalogEntry]:
    entries: list[WikiCatalogEntry] = []
    seen: set[str] = set()
    tables = _tables(text)
    for table in tables:
        table_text = str(table)
        if "TS4icon" not in table_text and "The Sims 4" not in table_text:
            continue
        rows = _rows_from_table(table)
        if not rows:
            continue
        header = {normalize(cell) for cell in rows[0]}
        if "career" not in header:
            continue
        for row in rows[1:]:
            if len(row) < 2:
                continue
            name = _first_name(row[1])
            key = normalize(name)
            if not key or key in seen or key in {normalize(h) for h in _HEADER_CELLS}:
                continue
            seen.add(key)
            entries.append(
                WikiCatalogEntry(
                    name=name,
                    pack=_pack_from_cell(row[-1]) if row else None,
                    category="career",
                )
            )
    if not entries:
        # Fallback: pages that use links such as "Business (career)".
        for link in mwparserfromhell.parse(text).filter_wikilinks():
            target = str(link.title).strip()
            if target.casefold().endswith("(career)"):
                name = clean_text(str(link.text)) if link.text else clean_text(target)
                key = normalize(name)
                if key and key not in seen:
                    seen.add(key)
                    entries.append(WikiCatalogEntry(name=name, category="career"))
    return entries


def parse_catalog_milestones(text: str) -> list[WikiCatalogEntry]:
    entries: list[WikiCatalogEntry] = []
    seen: set[str] = set()
    for table in _tables(text):
        for row in _rows_from_table(table):
            if len(row) < 2:
                continue
            name = _first_name(row[1])
            key = normalize(name)
            if not key or key in seen or key in {normalize(h) for h in _HEADER_CELLS}:
                continue
            if key == "pet" or "/" in name:
                continue
            seen.add(key)
            entries.append(
                WikiCatalogEntry(
                    name=name,
                    description=clean_text(row[2]) if len(row) > 2 else None,
                    pack=_pack_from_cell(row[-1]),
                    category="milestone",
                )
            )
    return entries


def parse_catalog_likes(text: str) -> list[WikiCatalogEntry]:
    entries: list[WikiCatalogEntry] = []
    seen: set[str] = set()
    liked_headers = {
        "activity",
        "color",
        "musicgenre",
        "dcorstyle",
        "decorstyle",
        "fashiontype",
    }
    for table in _tables(text):
        rows = _rows_from_table(table)
        if not rows:
            continue
        header = {normalize(cell) for cell in rows[0]}
        if "characteristic" in header:
            continue
        if not (header & liked_headers):
            continue
        for row in rows[1:]:
            if len(row) < 2:
                continue
            name = _first_name(row[1])
            key = normalize(name)
            if not key or key in seen or key in {normalize(h) for h in _HEADER_CELLS}:
                continue
            if key.startswith("patch") or "thesims" in key or key.endswith("event"):
                continue
            seen.add(key)
            entries.append(
                WikiCatalogEntry(
                    name=name,
                    pack=_pack_from_cell(row[-1]),
                    category="preference",
                )
            )
    return entries


def extract_premade_links(text: str, *, limit: int = 5000) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for link in mwparserfromhell.parse(text).filter_wikilinks():
        target = str(link.title).strip()
        if not target or target.startswith("#"):
            continue
        if target.casefold().startswith(_FILE_PREFIXES):
            continue
        target = target.split("#", 1)[0].strip()
        key = normalize_sim_name(target)
        if not key or key in seen:
            continue
        seen.add(key)
        links.append(target)
        if len(links) >= limit:
            break
    return links
