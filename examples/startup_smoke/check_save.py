"""Check that the smoke-test save contains a newly played Sim at Crick Cabana."""

import sys

from sims4_sdk.save import read_save


def main(path):
    save = read_save(path)
    household = save.active_household
    if household is None or household.premade_household_id:
        raise SystemExit("The save has no active custom household.")
    zone = save.zones.get(household.home_zone)
    if zone is None or zone.lot_id != 1064509568 or zone.household_id != household.household_id:
        raise SystemExit("The active household did not move into Crick Cabana.")
    sims = save.household_sims(household)
    if len(sims) != 1 or not sims[0].first_name:
        raise SystemExit("Expected one named Sim in the active household.")
    print(f"{sims[0].first_name} {sims[0].last_name} moved into {zone.name}.")


if __name__ == "__main__":
    main(sys.argv[1])
