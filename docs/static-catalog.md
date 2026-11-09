# Static catalog and pre-made Sims (Step 2)

Step 2 answers questions that do **not** require a save file:

- What traits, likes/dislikes, aspirations, careers, milestones, and relationship
  bits exist in the installed game, DLCs, and mods?
- Which pre-made Sims and households ship with the game?
- What are their base names, traits, likes/dislikes, skills, households, and
  family relationships?

All of it is extracted from the installation (`Data/`, `Delta/`, and `Mods/`)
and cached, so downstream tools can call it without a save.

## Revised roadmap

| Step | Scope | Status |
| --- | --- | --- |
| 1 | DBPF/RefPack/STBL/DATA/Combined Tuning readers | done |
| 2 | Static catalog + pre-made Sims (no save) | done |
| 3 | Saves, Tray files, live Sim state | next |
| 4 | Sims Wiki validation | pending |
| 5 | CLI and export helpers | pending |

Saves remain a first-class feature, but they are no longer a prerequisite for
reading the base definitions.

## Tuning sources

The catalog is built from `CombinedTuning` resources (`0x62E94D38`) in load
order:

1. base game full build,
2. base game preload,
3. base game delta,
4. each DLC pack (`Delta/EP*`, `GP*`, `SP*`, `FP*`), with delta last,
5. mods (`Mods/**/*.package`).

Later definitions override earlier ones. Individual tuning XML resources
(`0x03B33DDF`) are also read, which covers most mods.

### Classes extracted

| Class | Model | Main fields |
| --- | --- | --- |
| `Trait` | `Trait` | display name, description, `trait_type`, ages, species, conflicts, icon |
| `Preference` | `Preference` | like/dislike type, item, display name, ages, conflicts |
| `Aspiration` | `Aspiration` | display name, valid ages, objectives, track/category |
| `AspirationTrack` | `AspirationTrack` | display text, category, aspiration list, primary trait |
| `AspirationCategory` | `AspirationCategory` | display text, sort order |
| `Career` | `Career` | start track, category |
| `TunableCareerTrack` | `CareerTrack` | career name/description, level list |
| `CareerLevel` | `CareerLevel` | title, pay, schedule, promotion reward, level |
| `DevelopmentalMilestone` | `Milestone` | display name, category, ages, repeatable, primary |
| `RelationshipBit` | `RelationshipBit` | display name, description, depth, track |

All localized strings are resolved through the merged STBL tables for the chosen
locale. The default is `ENG_US`; pass another locale to `Sims4Workspace`.

## Pre-made Sims

The concrete pre-made population is defined by tuning, not by the user save:

| Class | Use |
| --- | --- |
| `PremadeSimTemplate` | one Sim: name, SimInfo resource, explicit traits/skills, aspiration, career level, dynasty, occult, pregnancy |
| `PremadeHouseholdTemplate` | household members and spouse/family relationships |
| `TunablePremadeAncestor` | family-tree ancestors (name, gender, death trait, thumbnail) |

### SimInfo (`.siminfo`, type `0x025ED6F4`)

`PremadeSimTemplate` points at a `.siminfo` resource. That resource contains the
traits that were baked into the Sim. The first uint32 is a version (currently
38); the second uint32 points at the **last** 64-bit trait ID in the trait list.
The list itself is:

```
uint8   count
uint64  trait_id    (count times)
```

Step 2 walks back from the header pointer, validates the count byte and checks
every ID against the catalog, then merges those traits with the template's
explicit list. This is how base-game Sims such as Bella Goth get their trait
list even though their template only says `num_random`.

Likes/dislikes are stored in the same trait list and are separated using the
`Preference` catalog entries.

### What is and is not available statically

- **Available:** names, baked traits, preferences, household membership,
  spouse/parent relationships, ancestors, explicit skills, explicit aspiration
  and career level, dynasty, occult, pregnancy.
- **Template-only:** some base-game Sims do not pin an aspiration or career in
  tuning; the game may assign one at runtime. In that case the field is `None`
  rather than guessed.
- **Step 3:** full SimInfo parsing (career/aspiration trackers), live
  relationships, milestones, and all save state.

## API

```python
from sims4_sdk import Sims4Workspace
from sims4_sdk.catalog import build_static

ws = Sims4Workspace()
data = ws.static_data()          # cached
catalog = data.catalog

catalog.summary()
catalog.trait("trait_Mean")
catalog.preference("trait_SimPreference_Likes_Music_HipHop")
catalog.aspiration("aspiration_Fortune_A1")
catalog.career_level("career_SecretAgent_Villain_Level3")
catalog.milestone("lifeMilestone_Engaged")

for sim in data.sims:
    print(sim.full_name, sim.household_name)
    print("  personality:", [t.display_name for t in sim.personality_traits])
    print("  visible:", [t.display_name for t in sim.visible_traits])
    print("  likes:", [p.display_name for p in sim.preferences if p.is_like])
    print("  dislikes:", [p.display_name for p in sim.preferences if p.is_dislike])

# Build a subset (useful for tests or single-pack tools)
from sims4_sdk import Installation
inst = Installation()
subset = [p for p in inst.packages if p.pack in {"BASE", "EP13"}]
data = build_static(inst, packages=subset, use_cache=False)
```

## Cache and validation

A full scan of the local installation (616 packages, including mods) produces:

| Item | Count |
| --- | --- |
| Tuning entries | 179,499 |
| Traits | 2,795 |
| Preferences | 334 |
| Aspirations | 392 |
| Careers | 146 |
| Career levels | 671 |
| Developmental milestones | 201 |
| Relationship bits | 766 |
| Pre-made Sims | 400 |
| Pre-made households | 191 |
| Pre-made ancestors | 41 |
| Errors | 0 |

The first build takes about four minutes; the cached load is under a second.
Pass `include_mods=False` to get game-only data, or a package subset to
`build_static` for faster iteration.

`Sims4Workspace` and `build_static` cache the result as
`%LOCALAPPDATA%\sims4-sdk\cache\static-<hash>.pkl`. The hash covers package
paths, modification times, sizes, the locale, and the cache schema version.
Deleting the folder (or passing `refresh=True`) forces a rebuild.
