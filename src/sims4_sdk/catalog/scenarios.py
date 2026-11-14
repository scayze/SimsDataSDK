"""Scenario tuning and the NPC templates referenced by scenarios.

References are retained even when their target is missing. A template chooser
may create a new Sim rather than select an existing premade; matching a
SimInfo key therefore establishes an appearance-template link, not identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ..core import ResourceKey, TuningElement
from ..core.images import parse_image_key
from ..export import Serializable
from .models import TuningSource
from .diagnostics import ExtractionIssue
from .values import TuningView


@dataclass
class Scenario(Serializable):
    id: int
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    role_ids: list[int] = field(default_factory=list)
    npc_filter_ids: list[int] = field(default_factory=list)
    household_keys: list[ResourceKey] = field(default_factory=list)
    starting_phase_id: Optional[int] = None
    source: Optional[TuningSource] = None


@dataclass
class ScenarioRole(Serializable):
    id: int
    name: str
    criteria: list[dict] = field(default_factory=list)
    source: Optional[TuningSource] = None


@dataclass
class SimFilter(Serializable):
    id: int
    name: str
    template_chooser_id: Optional[int] = None
    household_template_ids: list[int] = field(default_factory=list)
    source: Optional[TuningSource] = None


@dataclass
class SimTemplateChooser(Serializable):
    id: int
    name: str
    template_ids: list[int] = field(default_factory=list)
    source: Optional[TuningSource] = None


@dataclass
class SimTemplate(Serializable):
    id: int
    name: str
    siminfo_key: Optional[ResourceKey] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    source: Optional[TuningSource] = None


@dataclass
class NPCHouseholdTemplate(Serializable):
    id: int
    name: str
    sim_template_ids: list[int] = field(default_factory=list)
    source: Optional[TuningSource] = None


@dataclass
class WalkbyDirector(Serializable):
    id: int
    name: str
    situation_ids: list[int] = field(default_factory=list)
    source: Optional[TuningSource] = None


@dataclass
class SpecificSimSituation(Serializable):
    id: int
    name: str
    job_id: Optional[int] = None
    source: Optional[TuningSource] = None


@dataclass
class SituationJob(Serializable):
    id: int
    name: str
    filter_id: Optional[int] = None
    source: Optional[TuningSource] = None


@dataclass
class ScenarioData(Serializable):
    scenarios: dict[int, Scenario] = field(default_factory=dict)
    roles: dict[int, ScenarioRole] = field(default_factory=dict)
    sim_filters: dict[int, SimFilter] = field(default_factory=dict)
    template_choosers: dict[int, SimTemplateChooser] = field(default_factory=dict)
    sim_templates: dict[int, SimTemplate] = field(default_factory=dict)
    household_templates: dict[int, NPCHouseholdTemplate] = field(default_factory=dict)
    walkby_directors: dict[int, WalkbyDirector] = field(default_factory=dict)
    specific_sim_situations: dict[int, SpecificSimSituation] = field(default_factory=dict)
    situation_jobs: dict[int, SituationJob] = field(default_factory=dict)
    diagnostics: list[ExtractionIssue] = field(default_factory=list)

    def scenario(self, key: str | int) -> Optional[Scenario]:
        if isinstance(key, int):
            return self.scenarios.get(key)
        needle = key.casefold()
        for item in self.scenarios.values():
            if needle in (item.name.casefold(), (item.display_name or "").casefold()):
                return item
        return next(iter(self.find_scenarios(key)), None)

    def find_scenarios(self, query: str = "") -> list[Scenario]:
        needle = query.casefold()
        return sorted((item for item in self.scenarios.values()
                       if needle in item.name.casefold() or needle in (item.display_name or "").casefold()),
                      key=lambda item: (item.name.casefold(), item.id))


def _child(node, name):
    return next((item for item in node if item.get("n") == name), None) if node is not None else None


def _walk(view, node, depth=0):
    if depth >= 32:
        return
    node = view.resolve(node)
    if node is None:
        return
    yield node
    for child in node:
        yield from _walk(view, child, depth + 1)


def _named_numbers(view, node, name):
    values = []
    for parent in _walk(view, node):
        for child in parent:
            if child.get("n") == name:
                number = view.number_of(child)
                if number is not None and number not in values:
                    values.append(number)
    return values


def _list_numbers(view, node):
    values = []
    for item in _walk(view, node):
        if len(item) == 0:
            number = view.number_of(item)
            if number is not None and number not in values:
                values.append(number)
    return values


def _named_text(view, node, name):
    for parent in _walk(view, node):
        for child in parent:
            if child.get("n") == name:
                for value in _walk(view, child):
                    if len(value) == 0:
                        text = view.text_of(value)
                        if text:
                            return text
    return None


def _tree(view, node, depth=0):
    if depth >= 32:
        return None
    original = node
    node = view.resolve(node)
    if node is None:
        return None
    result = {"tag": node.tag}
    name = original.get("n") or node.get("n")
    if name:
        result["name"] = name
    if node.get("t"):
        result["variant"] = node.get("t")
    if node.text and node.text.strip():
        result["value"] = node.text.strip()
    children = [_tree(view, child, depth + 1) for child in node]
    if any(child is not None for child in children):
        result["children"] = [child for child in children if child is not None]
    return result


def extract_scenarios(entries: Mapping[int, TuningElement], sources: Mapping[int, TuningSource],
                      strings: Mapping[int, str]) -> ScenarioData:
    """Extract observed scenario and NPC tuning, retaining unresolved IDs."""
    data = ScenarioData()
    for instance, entry in entries.items():
        cls = entry.cls
        if cls not in {"Scenario", "ScenarioRole", "TunableSimFilter", "TunableTemplateChooser",
                       "TunableSimTemplate", "HouseholdTemplate", "SchedulingWalkbyDirector",
                       "SpecificSimCustomStatesSituation", "SituationJob"}:
            continue
        try:
            _extract_entry(data, instance, entry, sources.get(instance), strings)
        except Exception as exc:
            source = sources.get(instance)
            data.diagnostics.append(ExtractionIssue.from_exception(
                "scenario_tuning", exc, package_path=source.path if source else None,
                resource_key=source.resource_key if source else None, tuning_id=instance,
                recoverable=True))
    return data


def _extract_entry(data, instance, entry, source, strings):
    cls = entry.cls
    view = TuningView(entry, strings)
    if cls == "Scenario":
        household_keys = []
        for node in _walk(view, view.child("compatible_premade_household_templates")):
            key = parse_image_key(view.raw_text_of(node))
            if key is not None and key not in household_keys:
                household_keys.append(key)
        data.scenarios[instance] = Scenario(
            instance, entry.name, view.text("scenario_name"), view.text("scenario_description"),
            _named_numbers(view, view.child("scenario_role_data"), "role"),
            _named_numbers(view, view.child("scenario_npc_sims"), "sim_filter"),
            household_keys, view.number("starting_phase"), source)
    elif cls == "ScenarioRole":
        criteria = view.resolved_child("criteria")
        data.roles[instance] = ScenarioRole(instance, entry.name,
            [value for item in criteria for value in [_tree(view, item)] if value is not None]
            if criteria is not None else [], source)
    elif cls == "TunableSimFilter":
        data.sim_filters[instance] = SimFilter(
            instance, entry.name, view.number("_template_chooser"),
            _list_numbers(view, view.child("_household_templates_override")), source)
    elif cls == "TunableTemplateChooser":
        data.template_choosers[instance] = SimTemplateChooser(
            instance, entry.name, _named_numbers(view, view.child("_templates"), "template"), source)
    elif cls == "TunableSimTemplate":
        info = view.resolved_child("_sim_creation_info")
        key_node = _child(info, "resource_key")
        keys = [parse_image_key(view.raw_text_of(node)) for node in _walk(view, key_node)]
        data.sim_templates[instance] = SimTemplate(
            instance, entry.name, next((key for key in keys if key), None),
            _named_text(view, info, "first_name"), _named_text(view, info, "last_name"), source)
    elif cls == "HouseholdTemplate":
        data.household_templates[instance] = NPCHouseholdTemplate(
            instance, entry.name, _named_numbers(view, view.child("_household_members"), "sim_template"), source)
    elif cls == "SchedulingWalkbyDirector":
        data.walkby_directors[instance] = WalkbyDirector(
            instance, entry.name, _named_numbers(view, view.child("situation_shifts"), "situation"), source)
    elif cls == "SpecificSimCustomStatesSituation":
        data.specific_sim_situations[instance] = SpecificSimSituation(
            instance, entry.name, view.number("specific_sim_job"), source)
    else:
        data.situation_jobs[instance] = SituationJob(instance, entry.name, view.number("filter"), source)
