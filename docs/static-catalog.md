# Static catalog and pre-made Sims

The static catalog answers questions that do **not** require a save file:

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
| 5 | Public library API (serialization, lookups, portable snapshots) | done |

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
5. DLC pack-root packages (`EP*`, `GP*`, `SP*`, `FP*`), then their `Delta/` packages,
6. mods (`Mods/**/*.package`).

Later definitions override earlier ones. Individual tuning XML resources
(`0x03B33DDF`) are also read, which covers most mods.

Each extracted model's `source` identifies the package path and the full key
of the containing resource. For an entry inside Combined Tuning, the key is
the Combined Tuning resource's key; the entry's tuning ID is on the model.
This records the selected source, not a complete history of overridden entries.

Package scans are best effort. Inspect `static.catalog.diagnostics` for
structured `ExtractionIssue` records describing skipped packages, failed
resource reads, string tables, and model parsing. The stage, exception type,
message, package path, resource key and tuning ID are included when known.
`recoverable` is true when the operation continued after the issue, false when
it could not continue, and null when unknown; it does not mean the skipped data
was recovered. `unsupported_format` is populated only when a format is known
to be unsupported. Both fields serialize to JSON and may be null.
An empty diagnostics list does not establish that all game data is understood.

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
| `Skill`, `TunableSkill`, `Statistic` | `StatisticDefinition` | explicit tuning class, optional name, icon, ages and level type, source |

All localized strings are resolved through the merged STBL tables for the chosen
locale. The default is `ENG_US`; pass another locale to `Sims4Workspace`.

`catalog.statistics` enumerates these three explicit XML tuning classes from
combined and individual tuning. `catalog.statistic(id_or_name)` and
`catalog.find_statistics(query, is_skill=True)` provide lookup and filtering.
Only `Skill` and `TunableSkill` are classified as skills; for a generic
`Statistic`, `is_skill` is null because a name is not proof of its semantics.
`display_name_raw` retains the field or STBL key, and `display_name_field`
identifies `stat_name` or `display_name`; `display_name` is null if the field
or localization is unresolved. `ages` is null when absent or unresolved;
`skill_level_type` preserves the tuning value without claiming a curve mapping.
The source describes the selected winner under SDK package order. SimData-only
definitions, other restrictions, curve links, override history, and alternative
label fields are not decoded here.

`Catalog.visible_traits` excludes known internal trait types and naming patterns,
hidden traits, and IDs also catalogued as preferences. `Trait.is_internal` exposes
the trait-level part of that classification. This is conservative: unknown
internal traits may remain, and inclusion does not imply a trait is assignable.
For compatibility, `find_traits(visible_only=True)` still filters only the
`is_hidden` flag.

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

The reader walks back from the header pointer, validates the count byte and checks
every ID against the catalog, then merges those traits with the template's
explicit list. This is how base-game Sims such as Bella Goth get their trait
list even though their template only says `num_random`.

Likes/dislikes are stored in the same trait list and are separated using the
`Preference` catalog entries.

## Starter-save households and lots

`StaticData.world` preserves the selected starter household and lot records
alongside the merged premade view. Use `world.households[resource_instance]`
and `record.member(sim_id)` to inspect their parsed values, or
`world.find_members(sim_id)` to find all records containing that ID. These
records retain their original bytes as `.raw`; normal JSON export omits those
bytes, and `include_raw=True` includes them as hex. Records reflect the SDK's
selected load order. `world.household_resources` and `world.lot_resources` use
full resource keys, preserving records with different groups; the convenient
`households` and `lots` views use instance IDs and therefore select one record
when instances collide. These are winning records, not an archive of overrides
or an identity match to a tuning template. Older portable snapshots have
`world=None` and must be rebuilt to obtain this data.

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

`PremadeHousehold.localized_name` and `.description` resolve the associated
manifest's household strings. `.display_name` uses the localized name when
available and otherwise falls back to an inferred name. `.lot_ids` contains all
linked lot manifest IDs, while `.lot_id` is set only for a single link. If linked
manifests disagree on a localized name or description, that value is left unset
instead of choosing one arbitrarily. Older portable snapshots remain readable,
but need to be rebuilt to populate the new household links.

Each household member message carries:

| Field | Meaning |
| --- | --- |
| `5` / `6` | first name / last name |
| `55` / `56` | first name / last name STBL keys, when names are localized |
| `7` | gender flag (`0x1000` male, `0x2000` female) |
| `8` | age flag (`4` child, `8` teen, `16` young adult, `32` adult, `64` elder) |
| `12` | body/genetics float list |
| `30.10` | packed trait IDs (the age trait is included; preference IDs share this list) |
| `30.12` | career, career track, start level (`3` = 0-based track level, `4` = display level) |
| `30.13` | skill statistic ID + raw skill value |
| `30.14` | genealogy: repeated `(relation type, ancestor Sim ID)` — `0` mother, `1` father, `2/3` maternal grandparents, `4/5` paternal grandparents |
| `15` | spouse Sim ID |
| `34` | aspiration track ID |

`StarterMember.first_name_key` and `.last_name_key` preserve these keys even
if the selected locale has no matching string. During a static build the SDK
resolves them against the same merged locale table as the catalog, before
building premade Sim models. Inline names take precedence. An unresolved name
is empty and its key remains available; no name is guessed. Standalone callers
can pass `strings=` to `parse_premade_household`, or call
`WorldData.resolve_names(strings)` with a different locale's table. Rebuild a
cached static snapshot to populate names after upgrading.

Builds cache Combined Tuning parsing per unique resource content: several packs
ship the same blob in both `SimulationPreload.package` and
`SimulationDeltaBuild0.package`, so identical bytes are decoded once. SimInfo
lookups also read directly from their existing index entry instead of re-parsing
each package index. On a full install this cuts the cold build from roughly 285 s
to 130 s.

The SDK merges these into the normal models:

* `PremadeHousehold.funds` is populated from tuning
  (`PremadeHouseholdTemplate._household_funds`) and, when present, from the
  starter-save resource (`money`);
* a household whose members are all already defined by tuning (Goth,
  Landgraabs, Zest) is not duplicated — its funds and missing gender/age hints
  are attached to the tuning household instead;
* otherwise a `PremadeHousehold` plus one `PremadeSim` per member is added, with
  `gender`, `age`, `personality_traits`, `aspiration_track`, `career`,
  `career_track`, `career_level` (the exact starting job title), and raw skill
  values (`SkillLevel.value`);
* `spouse_id`/`spouse_name`, `parents`, `children`, `siblings` and
  `extended_family` are filled from the resource's spouse field and genealogy
  entries (children and siblings are derived). This also enriches tuning
  households such as Goth, which have both a template and a starter resource;
* `PremadeBundle.lots` exposes the lot records and their household links.

Preferences are stored as preference IDs in the *same* trait list. They are
present for households whose resource defines them (for example Caliente and
the Martínez scenario) and for tuning-based pre-mades through SimInfo. Some
older households — BFF, Pancakes, Roomies, Spencer-Kim-Lewis — define neither,
so their likes/dislikes only appear once the save has assigned them.

`PremadeSim.id` for these Sims is the 64-bit Sim ID from the resource, so it does
not collide with 32-bit tuning instance IDs.

### Initial relationship values

The numeric friendship/romance values are tuning data, not hardcoded, and the
SDK now exposes them:

- `Catalog.relationship_defaults` — per genealogy link (`Roommate` 15,
  `FamilyMember` 45, `Spouse` 75 romance, `Fiance` 75, `Steady` 40, pets 33).
- `Catalog.premade_relationships` — cross-household pairs from
  `PremadeSimRelationships.RELATIONSHIP_MAP`, with the resolved loot values.
- `Catalog.relationship_track_ranges` — the value interval of a relationship bit
  (for example `Lovebirds` romance 25–75, `It's Complicated` -50…-10).
- `HouseholdRelationship.friendship` / `.romance` and
  `.friendship_min` / `.friendship_max` / `.romance_min` / `.romance_max` on
  pre-made household links.
- `PremadeBundle.relationship(a, b)` and `.relationships_for(sim)`.

### Gender options and preferences

`PremadeSim.gender_options` / `SavedSim.gender_options` return a `GenderOptions`
view built from the `trait_GenderOptions_*` and `trait_SexualOrientation_*`
traits in the trait tracker:

| Field | Source traits |
| --- | --- |
| `gender` | `trait_GenderMale` / `trait_GenderFemale` |
| `frame` | `trait_GenderOptions_Frame_Masculine` / `_Feminine` |
| `clothing` | `trait_GenderOptions_Clothing_MensWear` / `_WomensWear` |
| `toilet_use` | `trait_GenderOptions_Toilet_Standing` / `_Sitting` |
| `lactation` | `trait_GenderOptions_Lactate_Can` / `_CanNot` |
| `attracted_to` / `not_attracted_to` | `trait_GenderOptions_AttractedTo_*` |
| `woohoo_interests` / `not_woohoo_interests` | `trait_SexualOrientation_WooHooInterests_*` |
| `sexuality` | `trait_GenderOptions_Sexuality_Exploring` / `_NotExploring` |
| `can_impregnate` | `trait_GenderOptions_Pregnancy_CanImpregnate` / `_CanNotImpregnate` |
| `can_be_impregnated` | `trait_GenderOptions_Pregnancy_CanBeImpregnated` / `_CanNot_BeImpregnated` |

The attraction and WooHoo interest fields are lists because a Sim can be
attracted to several genders at once. The remaining fields are single values; if
conflicting traits are present (some pre-made templates contain more than one
life-stage configuration), the last trait in the tracker wins.

For a relationship with a tracked bit the game adds a random score inside the
bit interval, so the final value is the default plus that random increment
(clamped to the track's -100…100 range).

Some packs (for example EP10) store the household resource under the **same name**
as the tuning template but leave the member names empty.  In that case the SDK
matches members by position, so the resource still supplies gender, age, body
blend, spouse and funds.  When such a record is merged into a tuning household,
lot references that point at the legacy resource ID are remapped to the tuning
household ID.

### What is and is not available statically

- **Available:** names, baked traits, preferences, gender options / attraction
  (when the template or SimInfo carries `trait_GenderOptions_*`), household
  membership, household funds, spouse/fiance/steady plus parent/child/sibling
  relationships with typed kinds (`MOTHER`/`FATHER`/`MOTHERS_FATHER`/...),
  dangling out-of-household targets (`PremadeSim.unlinked_relations`),
  ancestors, explicit skills, explicit aspiration and career level, dynasty,
  occult, pregnancy, gender and age (from starter-save resources), aspiration
  track, career track, lots, lot↔household links, initial relationship defaults
  and cross-household relationship values, and the steady/engagement/marriage
  bits plus family and romance trope IDs.
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
    print("  gender options:", sim.gender_options)

# Base-game households that have no tuning template
bff = data.household("BFF")
print(bff.funds, [member.full_name for member in bff.members])

# Lots and their occupying household
for lot in data.lots:
    print(lot.lot_name, "->", lot.household_name)

# Initial relationship values
pancakes = data.household("Pancakes")
spouse = next(rel for rel in pancakes.relationships if rel.kind == "spouse")
print(spouse.friendship, spouse.romance)      # 45.0 75.0

print(catalog.steady_bit_id, catalog.family_trope_ids, catalog.romance_trope_ids)

for relationship in data.premades.relationships_for(data.sim("Megumi Ito")):
    print(relationship.sim_a_name, "->", relationship.sim_b_name,
          relationship.friendship, relationship.romance)

# Build a subset (useful for tests or single-pack tools)
from sims4_sdk import Installation
inst = Installation()
subset = [p for p in inst.packages if p.pack in {"BASE", "EP13"}]
data = build_static(inst, packages=subset, use_cache=False)
```

### Serialization and lookups

Every catalog and pre-made model has `to_dict()` and `to_json()`. The dictionary
is JSON-safe (integer IDs become string keys) and excludes the large string
table and raw payloads unless requested:

```python
data.to_dict()                          # catalog + pre-mades
catalog.to_dict(include_strings=True)   # + the merged STBL table
catalog.to_dict(include_tuning_index=True)  # + every tuning ID → name/class
```

Lookups accept either a numeric ID or a tuning name. Exact names are tried first,
then a case-insensitive match; `find_*` filter by substring and pack:

```python
catalog.trait("TRAIT_MEAN")
catalog.aspiration_track("AspirationTrack_PublicEnemy")
catalog.find_traits("vampire", trait_type="OCCULT", pack="EP01")
catalog.find_milestones(category="CAREER")
catalog.packs()
```

### Icons

`Trait`, `Aspiration`, `AspirationTrack`, `CareerTrack`, `Milestone` and
`RelationshipBit` carry the raw tuning `icon` string plus a parsed
`icon_key` (`ResourceKey`, `None` when absent). `PremadeAncestor.thumbnail`
has the same treatment via `thumbnail_key`. Use the workspace to resolve the
pixels (DST is unshuffled to standard DDS, and Pillow can convert it to PNG):

```python
trait = catalog.trait("trait_Mean")
trait.icon_key          # ResourceKey(0x2F7D0004, 0, ...) or None
image = ws.icon_for(trait)   # GameImage(data=DDS bytes, format, width, height) or None
raw = ws.icon_bytes("2f7d0004:00000000:24132068c93561df")
image.save("mean_icon.dds")  # .dds/.png inferred when no suffix
png = ws.icon_png(trait)     # PNG bytes, or None if the icon is unavailable
# Alternatively: png = image.to_png()
```

### Portable snapshots

`StaticData.save()` writes the whole static catalog plus pre-made Sims,
households, ancestors, and lots to a pickle. It can be loaded later without an
installation and used to read saves or Tray files:

```python
from sims4_sdk import Sims4Workspace
from sims4_sdk.catalog import Catalog, StaticData

ws = Sims4Workspace()
ws.save_static("sims4-static.pkl")

offline = Sims4Workspace.from_static("sims4-static.pkl", user_dir=user_dir)
save = offline.read_save(offline.latest_save_path())

catalog = Catalog.load("catalog.pkl")    # catalog-only snapshot
```

Snapshots are trusted local artifacts generated by the SDK; use `to_dict()` /
`to_json()` for interchange with other programs.

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
| Relationship defaults | 16 |
| Premade relationship pairs | 348 |
| Relationship bit ranges | 25 |
| Errors | 0 |

The first build takes about four and a half minutes; the cached load is under a
second. Pass `include_mods=False` to get game-only data, or a package subset to
`build_static` for faster iteration.

`Sims4Workspace` and `build_static` cache the result as
`%LOCALAPPDATA%\sims4-sdk\cache\static-<hash>.pkl`. The hash covers package
paths, modification times, sizes, the locale, and the cache schema version.
Deleting the folder (or passing `refresh=True`) forces a rebuild.
