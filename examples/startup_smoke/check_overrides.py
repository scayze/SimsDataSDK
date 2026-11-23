"""Build a package to test new-save overrides, or check the resulting save."""

import argparse
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from sims4_sdk.catalog.relationships import FRIENDSHIP_TRACK_ID
from sims4_sdk.catalog.worlds import parse_premade_household
from sims4_sdk.core import DBPF, CombinedTuning, ResourceKey
from sims4_sdk.core.resource_types import COMBINED_TUNING_TYPE_ID, PREMADE_HOUSEHOLD_TYPE_ID
from sims4_sdk.mods import (
    premade_relationship_override,
    premade_template_override,
    starter_household_override,
    write_package,
)
from sims4_sdk.save import read_save

HOUSEHOLD = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 0, 0x01D9A0186BAD30CD)
GOTH = ResourceKey(PREMADE_HOUSEHOLD_TYPE_ID, 0, 0x01BD3F7EDED01430)
FUNDS = 76543
MEAN = 16857
NEAT = 16858
BELLA = 469189
NANCY = 468090
CLOSE_FRIENDS = 254853


def build(path):
    install = Path(os.environ["SIMS4_INSTALL_DIR"])
    simulation = DBPF(install / "Data/Simulation/SimulationDeltaBuild0.package")
    entry = next(simulation.iter_entries_for_types({COMBINED_TUNING_TYPE_ID}))
    tuning = CombinedTuning.parse(simulation.read_resource(entry))
    bella = tuning.find_by_instance_id(BELLA)
    client = DBPF(install / "Data/Client/ClientDeltaBuild0.package")
    traits = ET.fromstring(f'<U><L n="explicit"><T>{MEAN}</T></L><T n="num_random">0</T></U>')
    raw = client.read_resource(GOTH)
    member = next(sim for sim in parse_premade_household(raw).members if sim.first_name == "Bella")
    # Use a different marker for the baked and tuning paths.
    print(write_package(path, [
        starter_household_override(HOUSEHOLD, client.read_resource(HOUSEHOLD), funds=FUNDS),
        starter_household_override(GOTH, raw, sim_traits={member.sim_id: [*member.trait_ids, NEAT]}),
        premade_template_override(bella, {"_traits": traits}),
        premade_relationship_override(tuning, {(BELLA, NANCY): CLOSE_FRIENDS}),
    ]))


def check(path, log=None):
    save = read_save(path)
    household = next((h for h in save.households.values() if h.premade_household_id == HOUSEHOLD.instance), None)
    bella = save.sim("Bella Goth")
    nancy = save.sim("Nancy Landgraab")
    errors = []
    if household is None or household.money != FUNDS:
        errors.append(f"BFF funds: {household.money if household else None}, expected {FUNDS}")
    if bella is None or NEAT not in bella.trait_ids:
        errors.append(f"Bella's baked Neat trait missing: {bella.trait_ids if bella else None}")
    if log is not None and f"Sim template {BELLA} explicit traits: ({MEAN},)" not in log.read_text(encoding="utf-8"):
        errors.append(f"Bella's XML template was not verified in {log}")
    relationship = next((r for r in bella.relationships if r.target_id == nancy.sim_id), None) if bella and nancy else None
    if relationship is None or not any(
        t.track_id == FRIENDSHIP_TRACK_ID and t.value == 60 for t in relationship.track_values
    ):
        errors.append("Bella and Nancy did not start with 60 friendship")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Verified BFF funds, Bella's baked trait, and relationship loot in {path}")
    if log is not None:
        print(f"Verified the loaded Sim template in {log}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check"])
    parser.add_argument("path", type=Path)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        build(args.path)
    else:
        check(args.path, args.log)
