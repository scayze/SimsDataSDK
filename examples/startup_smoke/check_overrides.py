"""Build a package to test new-save overrides, or check the resulting save.

``build`` writes the package and, next to it, a JSON file with the values the
check expects. Some edits pick their IDs from the installed game data, so pass
that JSON file to ``check`` with ``--expect``.
"""

import argparse
import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from sims4_sdk import Sims4Workspace
from sims4_sdk.catalog.lot_traits import LOT_TRAITS_MODULE, LOT_TRAITS_SIMDATA_KEY
from sims4_sdk.catalog.relationships import FRIENDSHIP_TRACK_ID, ROMANCE_TRACK_ID
from sims4_sdk.catalog.worlds import StarterCareer, parse_premade_household
from sims4_sdk.core import DBPF, CombinedTuning, ResourceKey
from sims4_sdk.core.resource_types import COMBINED_TUNING_TYPE_ID, PREMADE_HOUSEHOLD_TYPE_ID
from sims4_sdk.mods import (
    StarterMemberEdit,
    initial_lot_traits_override,
    premade_relationship_override,
    premade_template_override,
    relationship_loot,
    starter_household_override,
    starter_household_text,
    write_package,
)
from sims4_sdk.save import read_save
from sims4_sdk.skill_discovery import discover_skill_curves

HOUSEHOLD = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 0, 0x01D9A0186BAD30CD)  # BFF
GOTH = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 0, 0x01BD3F7EDED01430)
FUNDS = 76543
MEAN = 16857
NEAT = 16858
BELLA = 469189
NANCY = 468090
FRIENDSHIP = 60
ROMANCE = 15
SKILL_LEVEL = 4
CAREER_LEVEL = 2  # 0-based track level, shown as level 3
NAME = "SDK Smoke Friends"
DESCRIPTION = "Household text written by the sims4_sdk startup smoke test."


def _tuning_with_module(install, module):
    """Return the first combined tuning (delta, then full build) with ``module``."""
    for name in ("SimulationDeltaBuild0.package", "SimulationFullBuild0.package"):
        path = install / "Data/Simulation" / name
        if not path.exists():
            continue
        package = DBPF(path)
        for entry in package.iter_entries_for_types({COMBINED_TUNING_TYPE_ID}):
            tuning = CombinedTuning.parse(package.read_resource(entry))
            if module is None or tuning.find_module(module) is not None:
                return tuning
    raise SystemExit(f"No combined tuning holds {module}")


def _member_edit(ws, member):
    catalog = ws.catalog
    curves = discover_skill_curves(ws.installation.packages)
    skill, curve = next(((skill, curve) for skill in catalog.find_statistics("painting", is_skill=True)
                         for curve in [curves.for_skill(skill, allow_incomplete=True)]
                         if curve is not None and curve.max_level >= SKILL_LEVEL), (None, None))
    career = next((career for career in catalog.find_careers("painter")
                   if career.start_track_id and career.id not in {c.career_id for c in member.careers}), None)
    track = next((track for track in catalog.aspiration_tracks.values()
                  if "paint" in track.name.casefold() and track.id != member.aspiration_track_id), None)
    if skill is None or career is None or track is None:
        raise SystemExit("The installation is missing the painting skill, career, or aspiration")
    xp = curve.xp_for_level(SKILL_LEVEL)
    edit = StarterMemberEdit(
        skills={skill.id: xp},
        careers=[StarterCareer(career.id, career.start_track_id, CAREER_LEVEL)],
        aspiration_track_id=track.id,
    )
    expected = {"skill_id": skill.id, "skill_xp": xp, "career_id": career.id,
                "track_id": career.start_track_id, "aspiration_track_id": track.id}
    return edit, expected


def _lot_traits(ws, lot):
    defaults = set(ws.catalog.initial_lot_trait_ids.get(lot.house_description_id, ()))
    candidates = sorted((trait for trait in ws.catalog.lot_traits.values()
                         if not trait.is_challenge and trait.id not in defaults),
                        key=lambda trait: (trait.source is None or trait.source.pack != "BASE", trait.id))
    if len(candidates) < 2:
        raise SystemExit("The installation has fewer than two unused lot traits")
    return [trait.id for trait in candidates[:2]]


def build(path):
    install = Path(os.environ["SIMS4_INSTALL_DIR"])
    ws = Sims4Workspace(install_dir=install, include_mods=False)
    tuning = _tuning_with_module(install, None)
    lot_tuning = _tuning_with_module(install, LOT_TRAITS_MODULE)
    bella = tuning.find_by_instance_id(BELLA)
    client = DBPF(install / "Data/Client/ClientDeltaBuild0.package")
    traits = ET.fromstring(f'<U><L n="explicit"><T>{MEAN}</T></L><T n="num_random">0</T></U>')

    raw = client.read_resource(GOTH)
    goth_member = next(sim for sim in parse_premade_household(raw).members if sim.first_name == "Bella")
    starter = client.read_resource(HOUSEHOLD)
    member = parse_premade_household(starter).members[0]
    edit, expected = _member_edit(ws, member)

    lot = next((lot for lot in ws.lot_registry().lots
                if lot.starter_household_id == HOUSEHOLD.instance), None)
    if lot is None:
        raise SystemExit("BFF's starter lot is not installed")
    manifest = ws.static_data().world.lot_resources[lot.manifest_key]
    lot_traits = _lot_traits(ws, lot)
    loot_key, loot = relationship_loot("sims4_sdk_smoke:BellaNancy",
                                       friendship=FRIENDSHIP, romance=ROMANCE)

    expected.update(member=f"{member.first_name} {member.last_name}", lot_traits=lot_traits,
                    house_description_id=lot.house_description_id)
    # Use a different marker for the baked and tuning paths.
    output = write_package(path, [
        starter_household_override(HOUSEHOLD, starter, funds=FUNDS, members={member.sim_id: edit}),
        *starter_household_text((lot.manifest_key, manifest.raw), name=NAME, description=DESCRIPTION),
        starter_household_override(GOTH, raw, members={
            goth_member.sim_id: StarterMemberEdit(trait_ids=[*goth_member.trait_ids, NEAT])}),
        premade_template_override(bella, {"_traits": traits}),
        (loot_key, loot),
        premade_relationship_override(tuning, {(BELLA, NANCY): loot_key.instance}),
        *initial_lot_traits_override(lot_tuning, ws.installation.find_resource(*LOT_TRAITS_SIMDATA_KEY),
                                     {lot.house_description_id: lot_traits}),
    ])
    Path(f"{output}.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    print(output)


def _track(relationship, track_id):
    return next((t.value for t in relationship.track_values if t.track_id == track_id), None)


def check(path, expect, log=None):
    expected = json.loads(expect.read_text(encoding="utf-8"))
    save = read_save(path)
    household = next((h for h in save.households.values() if h.premade_household_id == HOUSEHOLD.instance), None)
    bella = save.sim("Bella Goth")
    nancy = save.sim("Nancy Landgraab")
    member = save.sim(expected["member"])
    errors = []
    if household is None or household.money != FUNDS:
        errors.append(f"BFF funds: {household.money if household else None}, expected {FUNDS}")
    if household is None or household.name != NAME:
        errors.append(f"BFF name: {household.name if household else None!r}, expected {NAME!r}")
    if household is None or household.description != DESCRIPTION:
        errors.append(f"BFF description: {household.description if household else None!r}")
    if member is None:
        errors.append(f"BFF member {expected['member']} missing")
    else:
        skill = next((s for s in member.skills if s.skill_id == expected["skill_id"]), None)
        if skill is None or abs(skill.value - expected["skill_xp"]) > 0.5:
            errors.append(f"{expected['member']} skill {expected['skill_id']}: "
                          f"{skill.value if skill else None}, expected {expected['skill_xp']}")
        if not any(c.career_id == expected["career_id"] and c.track_id == expected["track_id"]
                   and c.track_level == CAREER_LEVEL for c in member.careers):
            errors.append(f"{expected['member']} careers: "
                          f"{[(c.career_id, c.track_id, c.track_level) for c in member.careers]}")
        if member.primary_aspiration_track_id != expected["aspiration_track_id"]:
            errors.append(f"{expected['member']} aspiration: {member.primary_aspiration_track_id}, "
                          f"expected {expected['aspiration_track_id']}")
    zone = save.zones.get(household.home_zone) if household and household.home_zone else None
    if zone is None or sorted(zone.lot_trait_ids) != sorted(expected["lot_traits"]):
        errors.append(f"BFF lot traits: {zone.lot_trait_ids if zone else None}, "
                      f"expected {expected['lot_traits']}")
    if bella is None or NEAT not in bella.trait_ids:
        errors.append(f"Bella's baked Neat trait missing: {bella.trait_ids if bella else None}")
    if log is not None and f"Sim template {BELLA} explicit traits: ({MEAN},)" not in log.read_text(encoding="utf-8"):
        errors.append(f"Bella's XML template was not verified in {log}")
    relationship = next((r for r in bella.relationships if r.target_id == nancy.sim_id), None) if bella and nancy else None
    tracks = (_track(relationship, FRIENDSHIP_TRACK_ID), _track(relationship, ROMANCE_TRACK_ID)) if relationship else None
    if tracks != (FRIENDSHIP, ROMANCE):
        errors.append(f"Bella and Nancy friendship/romance: {tracks}, expected {(FRIENDSHIP, ROMANCE)}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Verified BFF funds, text, member edits, lot traits, Bella's baked trait, "
          f"and the generated relationship loot in {path}")
    if log is not None:
        print(f"Verified the loaded Sim template in {log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--expect", type=Path, help="JSON file written by build")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        build(args.path)
    elif args.expect is None:
        parser.error("check needs --expect <package>.json")
    else:
        check(args.path, args.expect, args.log)
