"""Inspect a Sims 4 save and the Tray library.

Usage::

    python examples/inspect_save.py
    python examples/inspect_save.py --path "Slot_00000002.save"
    python examples/inspect_save.py --name Bella
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sims4_sdk import Sims4Workspace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", help="specific .save file (default: first save)")
    parser.add_argument("--name", help="filter Sims by name")
    parser.add_argument("--tray", action="store_true", help="also summarize the Tray library")
    parser.add_argument("--refresh", action="store_true", help="ignore the catalog cache")
    args = parser.parse_args()

    workspace = Sims4Workspace()
    catalog = workspace.static_data(refresh=args.refresh).catalog

    path = Path(args.path) if args.path else next(iter(workspace.save_files()), None)
    if path is None:
        print("No save files found. Pass --path explicitly.")
        return 1

    save = workspace.read_save(path, catalog)
    print(save.summary())
    print(f"slot: {save.slot.slot_name!r}  active household: {save.slot.active_household_id}")

    sims = list(save.sims.values())
    if args.name:
        needle = args.name.casefold()
        sims = [sim for sim in sims if needle in sim.full_name.casefold()]

    for sim in sims:
        print(f"\n{sim.full_name}  ({sim.age}, {sim.gender}, {sim.species})")
        print(f"  household: {sim.household_name}")
        print(f"  traits: {', '.join(t.display_name for t in sim.visible_traits) or '-'}")
        if sim.likes:
            print(f"  likes: {', '.join(p.display_name for p in sim.likes)}")
        if sim.dislikes:
            print(f"  dislikes: {', '.join(p.display_name for p in sim.dislikes)}")
        if sim.aspiration_track:
            print(f"  aspiration track: {sim.aspiration_track.display_name}")
        if sim.career:
            print(f"  career: {sim.career.track_name} / {sim.career.title} (level {sim.career.user_display_level})")
        if sim.skills:
            print(f"  skills: {', '.join(f'{s.name}={s.value:g}' for s in sim.skills if s.name)}")
        if sim.spouse_name:
            print(f"  spouse: {sim.spouse_name}")
        if sim.children:
            print(f"  children: {', '.join(child.name or str(child.sim_id) for child in sim.children)}")

    households = list(save.households.values())
    print(f"\nHouseholds ({len(households)}):")
    for household in households[:25]:
        print(f"  {household.name}: {', '.join(household.members)}")

    if args.tray:
        tray = workspace.tray_library()
        print(f"\n{tray.summary()}")
        for household in tray.households[:10]:
            title = household.item.title if household.item else household.family_name
            print(f"  {title}: {', '.join(sim.full_name for sim in household.sims)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
