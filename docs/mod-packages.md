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
from sims4_sdk.catalog.relationships import RELATIONSHIPS_MODULE
from sims4_sdk.mods import (
    premade_relationship_override,
    premade_template_override,
    starter_household_override,
    write_package,
)

ws = Sims4Workspace(include_mods=False)
collected = ws.extract_static().collected
key = ResourceKey(0xB3C438F0, 0, 0x01D9A0186BAD30CD)  # BFF
starter = ws.installation.find_resource(*key)
bella = collected.entries[469189]
relationships = collected.relationship_modules[RELATIONSHIPS_MODULE]

write_package("new-save.package", [
    starter_household_override(key, starter, funds=76543),
    premade_template_override(bella, {
        "_traits": ET.fromstring('<U><L n="explicit"><T>16857</T></L>'
                                 '<T n="num_random">0</T></U>'),
    }),
    premade_relationship_override(relationships, {
        (469189, 468090): 254853,  # Bella, Nancy, CloseFriends loot
    }),
])
```

- **Starter households** use the resource's full key. The helper updates funds,
  the embedded name, or baked trait and preference IDs for existing members.
  For `sim_traits`, pass the member's stored `sim_id` and the complete trait
  list. Read those with `parse_premade_household(starter).members`. Preserve
  age, species, and other internal traits when changing personality traits or
  preferences. A placed household can take its display name from a localized
  lot manifest. BFF does so on the tested game build.
- **Sim and household tuning** takes a source `TuningElement` and a mapping of
  top-level tunable names to XML nodes. This supports fields such as
  `_skills`, `career_level`, `primary_aspiration`, `occult`, and a tuning
  household's `_household_members` and `_household_relationship`. Copy the
  shape and value types from the installed game. Use the group for the target
  resource, with group 0 as the default. The example changes Bella's loaded
  XML tuning, while the Goth starter resource supplies her saved traits.
- **Cross-household relationships** use ordered Sim template ID pairs and an
  existing relationship loot ID. A `None` value removes that pair. The helper
  writes the full relationship module and preserves other pairs and family
  fixups. The example uses template IDs as distinct from baked member IDs.

Export against the intended game patch and installed packs. Overrides of the
same resource key can conflict, including two packages that edit different
pairs in the relationship module. Combine changes for each resource before
exporting and test the package using a fresh save. For game verification, see
the [startup smoke test](../examples/startup_smoke/README.md).
