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
| 3 | Saves, Tray files, live Sim state | done |
| 4 | Sims Wiki validation | done |
| 5 | CLI and export helpers | pending |

Saves remain a first-class feature, but they are no longer a prerequisite for
reading the base definitions.

## Tuning sources

The catalog is built from `CombinedTuning` resources (`0x62E94D38`) in load
order:

1. base game full build,
2. base game preload,
3. base game delta,
4. base game client full/delta builds (no tuning, but the pre-made household
   and lot-manifest resources live here),
5. each DLC pack (`Delta/EP*`, `GP*`, `SP*`, `FP*`), with delta last,
6. mods (`Mods/**/*.package`).

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

## Starter-save households and lots

Older packs (base game through EP18, plus GP04/07/08/09/11/12) do **not** use
`PremadeSimTemplate` for their pre-made population.  The BFF household, the
Pancakes, the Calientes, the Roomies and the Spencer-Kim-Lewis family have no
tuning template at all.  They are defined by two non-tuning resources:

| Type | Resource | Contents |
| --- | --- | --- |
| `0x729F6C4F` | lot/household manifest | one record per lot: lot name/description keys, household name/description keys, and a `uint64` reference to the household resource |
| `0xB3C438F0` | pre-made household | protobuf document: household name and funds, one message per member |

These live in `Data/Client/ClientFullBuild0.package` and
`Data/Client/ClientDeltaBuild0.package` (and `Delta/<PACK>/ClientDeltaBuild0.package`).
Scanning only `Data/Simulation` silently hides them, which is why earlier builds
were missing most base-game households.

Each household member message carries:

| Field | Meaning |
| --- | --- |
| `5` / `6` | first name / last name |
| `7` | gender flag (`0x1000` male, `0x2000` female) |
| `8` | age flag (`4` child, `8` teen, `16` young adult, `32` adult, `64` elder) |
| `12` | body/genetics float list |
| `30.10` | packed trait IDs (the age trait is included) |
| `30.12` | career + career track IDs |
| `30.13` | skill statistic ID + raw skill value |
| `34` | aspiration track ID |

The SDK merges these into the normal models:

* `PremadeHousehold.funds` is populated;
* a household whose members are all already defined by tuning (Goth,
  Landgraabs, Zest) is not duplicated — its funds and missing gender/age hints
  are attached to the tuning household instead;
* otherwise a `PremadeHousehold` plus one `PremadeSim` per member is added, with
  `gender`, `age`, `personality_traits`, `aspiration_track`, `career`,
  `career_track` and raw skill values (`SkillLevel.value`);
* `PremadeBundle.lots` exposes the lot records and their household links.

`PremadeSim.id` for these Sims is the 64-bit Sim ID from the resource, so it does
not collide with 32-bit tuning instance IDs.

### What is and is not available statically

- **Available:** names, baked traits, preferences, household membership,
  household funds, spouse/parent relationships, ancestors, explicit skills,
  explicit aspiration and career level, dynasty, occult, pregnancy, gender and
  age (from starter-save resources), aspiration track, career track, lots and
  lot↔household links.
- **Template-only:** some newer-pack Sims (EP19+) do not pin an aspiration,
  career, gender or age in tuning and have no starter-save resource; the field
  is `None` rather than guessed.
- **Not decoded yet:** the starter-save appearance/CAS blobs, skill level
  thresholds (raw `SkillLevel.value` is exposed instead), and `.world` terrain
  and lot-object data.

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
    print("  age/gender:", sim.age, sim.gender)
    print("  personality:", [t.display_name for t in sim.personality_traits])
    print("  visible:", [t.display_name for t in sim.visible_traits])
    print("  aspiration track:", sim.aspiration_track.display_name if sim.aspiration_track else None)
    print("  career:", sim.career_track.display_name if sim.career_track else None)

# Base-game households that have no tuning template
bff = data.household("BFF")
print(bff.funds, [member.full_name for member in bff.members])

# Lots and their occupying household
for lot in data.lots:
    print(lot.lot_name, "->", lot.household_name)

# Build a subset (useful for tests or single-pack tools)
from sims4_sdk import Installation
inst = Installation()
subset = [p for p in inst.packages if p.pack in {"BASE", "EP13"}]
data = build_static(inst, packages=subset, use_cache=False)
```

## Cache and validation

A full scan of the local installation (`include_mods=False`, 602 packages)
produces:

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
| Pre-made Sims | 431 |
| Pre-made households | 204 |
| Pre-made ancestors | 41 |
| Lots (lot manifest) | 548 |
| Errors | 0 |

The first build takes about four and a half minutes; the cached load is under a
second. Pass `include_mods=False` to get game-only data, or a package subset to
`build_static` for faster iteration.

`Sims4Workspace` and `build_static` cache the result as
`%LOCALAPPDATA%\sims4-sdk\cache\static-<hash>.pkl`. The hash covers package
paths, modification times, sizes, the locale, and the cache schema version.
Deleting the folder (or passing `refresh=True`) forces a rebuild.
