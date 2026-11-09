"""Print the save-independent catalog and the installed pre-made Sims.

Usage::

    python examples/static_catalog.py
    python examples/static_catalog.py --name Bella
    python examples/static_catalog.py --pack EP13

The first run scans the installation and writes a cache; later runs are fast.
"""

from __future__ import annotations

import argparse

from sims4_sdk import Sims4Workspace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", help="filter pre-made Sims by name")
    parser.add_argument("--pack", help="filter pre-made Sims by source pack (e.g. EP13)")
    parser.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = parser.parse_args()

    workspace = Sims4Workspace()
    data = workspace.static_data(refresh=args.refresh)
    catalog = data.catalog

    print(data.summary())
    print(f"errors: {len(catalog.errors)}")

    print("\nCatalog samples:")
    for name in (
        "trait_Mean",
        "trait_SimPreference_Likes_Music_HipHop",
        "aspiration_Fortune_A1",
        "career_SecretAgent_Villain_Level3",
        "lifeMilestone_Engaged",
    ):
        item = (
            catalog.trait(name)
            or catalog.preference(name)
            or catalog.aspiration(name)
            or catalog.career_level(name)
            or catalog.milestone(name)
        )
        if item is not None:
            print(f"  {type(item).__name__}: {name} -> {getattr(item, 'display_name', None) or getattr(item, 'title', None)}")

    sims = data.sims
    if args.name:
        needle = args.name.casefold()
        sims = [
            sim
            for sim in sims
            if needle in sim.full_name.casefold() or needle in sim.name.casefold()
        ]
    if args.pack:
        sims = [
            sim
            for sim in sims
            if sim.source is not None and sim.source.pack == args.pack.upper()
        ]

    print(f"\nPre-made Sims ({len(sims)}):")
    for sim in sims:
        traits = ", ".join(trait.display_name for trait in sim.visible_traits) or "-"
        print(f"  {sim.full_name} [{sim.household_name or 'no household'}]")
        print(f"    traits: {traits}")
        if sim.preferences:
            print(f"    preferences: {', '.join(p.display_name for p in sim.preferences)}")
        if sim.aspiration is not None:
            print(f"    aspiration: {sim.aspiration.display_name}")
        elif sim.aspiration_track is not None:
            print(f"    aspiration track: {sim.aspiration_track.display_name}")
        if sim.career_level is not None:
            print(f"    career: {sim.career_level.title} (level {sim.career_level.level})")
        elif sim.career_track is not None:
            print(f"    career: {sim.career_track.display_name}")

    print("\nHouseholds:")
    for household in data.households:
        members = ", ".join(member.full_name or "?" for member in household.members)
        funds = f" ({household.funds:,} simoleons)" if household.funds is not None else ""
        print(f"  {household.name}: {members or '(no members)'}{funds}")

    print("\nLots:")
    for lot in data.lots:
        print(f"  {lot.lot_name or '?'} -> {lot.household_name or '(empty)'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
