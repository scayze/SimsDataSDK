"""Build the Garden Essence to Brook Bungalow fixture or verify its fresh save."""

import argparse
from pathlib import Path

from sims4_sdk import Sims4Workspace
from sims4_sdk.mods import move_starter_household, write_package

ORIGIN_ID = 961473792  # Garden Essence
DESTINATION_ID = 1087874032  # Brook Bungalow


def build(ws, path):
    registry = ws.lot_registry()
    origin, destination = registry.lot(ORIGIN_ID), registry.lot(DESTINATION_ID)
    if origin is None or destination is None:
        raise SystemExit("The installation is missing the Willow Creek fixture lots.")
    print(write_package(path, move_starter_household(ws.static_data().world, origin, destination)))


def check(ws, path):
    save = ws.read_save(path)
    registry = ws.lot_registry(save)
    origin, destination = registry.lot(ORIGIN_ID), registry.lot(DESTINATION_ID)
    if origin is None or destination is None or origin.occupancy != "vacant":
        raise SystemExit("The move did not leave Garden Essence vacant.")
    bff = save.households.get(destination.household_id)
    if (bff is None or bff.premade_household_id != origin.starter_household_id
            or bff.home_zone != destination.zone_id):
        raise SystemExit("Brook Bungalow is not BFF's saved home zone.")
    print("BFF moved to Brook Bungalow, and Garden Essence is vacant.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "check"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    workspace = Sims4Workspace(include_mods=False)
    (build if args.action == "build" else check)(workspace, args.path)
