# Mod packages and new-save overrides

`sims4_sdk.mods.write_package(path, resources)` builds a DBPF 2.1 package from
`(ResourceKey, bytes)` pairs. Use a new `.package` path in an existing directory
on a filesystem that supports hard links. The writer publishes the completed
package atomically and raises `FileExistsError` if the destination is taken.
Copy the result into the game's Mods folder and enable custom content and mods.
The package produced by this example requires no script or in-game command.

```python
from xml.etree import ElementTree as ET

from sims4_sdk import ResourceKey, Sims4Workspace
from sims4_sdk.catalog.lot_traits import LOT_TRAITS_MODULE
from sims4_sdk.catalog.relationships import RELATIONSHIPS_MODULE
from sims4_sdk.catalog.worlds import StarterCareer, parse_premade_household
from sims4_sdk.skill_discovery import discover_skill_curves
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

ws = Sims4Workspace(include_mods=False)
static = ws.static_data()
collected = ws.extract_static().collected
key = ResourceKey(0xB3C438F0, 0, 0x01D9A0186BAD30CD)  # BFF
starter = ws.installation.find_resource(*key)
member = parse_premade_household(starter).members[0]
lot = next(lot for lot in ws.lot_registry().lots
           if lot.starter_household_id == key.instance)
manifest = static.world.lot_resources[lot.manifest_key]
curves = discover_skill_curves(ws.installation.packages)
painting = curves.for_skill(ws.catalog.statistic(16700))
bella = collected.entries[469189]
loot_key, loot = relationship_loot("my_mod:Bella_Nancy_Rivals",
                                   friendship=-40, bit_ids=[])

write_package("new-save.package", [
    starter_household_override(key, starter, funds=76543, members={
        member.sim_id: StarterMemberEdit(
            skills={16700: painting.xp_for_level(4)},
            careers=[StarterCareer(career_id=27930, track_id=27936, track_level=2)],
            aspiration_track_id=27896,
        ),
    }),
    *starter_household_text((lot.manifest_key, manifest.raw),
                            name="Best Friends", description="Two friends, one house."),
    premade_template_override(bella, {
        "_traits": ET.fromstring('<U><L n="explicit"><T>16857</T></L>'
                                 '<T n="num_random">0</T></U>'),
    }),
    (loot_key, loot),
    premade_relationship_override(collected.tuning_modules[RELATIONSHIPS_MODULE], {
        (469189, 468090): loot_key.instance,  # Bella, Nancy
    }),
    initial_lot_traits_override(collected.tuning_modules[LOT_TRAITS_MODULE], {
        lot.house_description_id: [ws.catalog.lot_trait("lottrait_Romantic").id],
    }),
])
```

The IDs above are illustrative; look them up in `ws.catalog` for your build.

- **Starter households** use the resource's full key. The helper updates
  funds, the inline name and description, and existing members. `members`
  maps the member's stored `sim_id` (from
  `parse_premade_household(starter).members`) to a `StarterMemberEdit`:
  - `trait_ids` replaces the complete trait list. Preserve age, species,
    preference, and other internal traits.
  - `skills` maps skill IDs to raw XP, the unit the record stores. Unlisted
    skills stay; `None` removes one. Convert levels with
    `SkillCurve.xp_for_level`. Base game skills store 100 XP for level 1.
  - `careers` replaces the current careers (an empty list removes them).
    `track_level` is 0-based; `display_level` defaults to `track_level + 1`.
    Career history and the other fields of an existing entry for the same
    career are kept.
  - `aspiration_track_id` sets the primary aspiration track.
- **Displayed household text** comes from the lot manifest (the house
  description), not the household record: only two shipped records carry an
  inline description at all. `starter_household_text` points the manifest at
  new strings and returns the edited manifest plus one string table per
  locale. To move a household and rename it, pass the destination manifest
  returned by `move_starter_household`.
- **Sim and household tuning** takes a source `TuningElement` and a mapping of
  top-level tunable names to XML nodes. This supports fields such as
  `_skills`, `career_level`, `primary_aspiration`, `occult`, and a tuning
  household's `_household_members` and `_household_relationship`. Copy the
  shape and value types from the installed game. Use the group for the target
  resource, with group 0 as the default.
- **Cross-household relationships** use ordered Sim template ID pairs and a
  relationship loot ID. A `None` value removes that pair. The helper writes
  the full relationship module and preserves other pairs and family fixups.
  Use an existing loot or build one with `relationship_loot`, which sets exact
  friendship and romance values (-100 to 100) and adds relationship bits. The
  module only accepts Sim templates (`PremadeSimTemplate`), so this cannot
  link Sims of classic households that have no template; those start without
  cross-household relationships.
- **Starting lot traits** for a new save come from the
  `INITIAL_ZONE_MODIFIERS` module tuning, keyed by house description ID
  (`WorldLot.house_description_id`). `initial_lot_traits_override` replaces
  the complete list for each listed lot and keeps every other lot. Read the
  defaults from `Catalog.initial_lot_trait_ids` and the available traits and
  challenges from `Catalog.lot_traits`.

Export against the intended game patch and installed packs. Overrides of the
same resource key can conflict, including two packages that edit different
pairs in the relationship module. Combine changes for each resource before
exporting and test the package using a fresh save. For game verification, see
the [startup smoke test](../examples/startup_smoke/README.md). The new loot,
manifest text, and starting lot trait exports are verified against game data
but not yet covered by the smoke test.
