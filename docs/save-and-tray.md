# Saves and Tray files (Step 3)

Step 3 adds the live data that only exists in a playthrough or a Gallery export.

## Save files

A `.save` file is a DBPF container. The main payload is a `SaveGameData`
protobuf in resource type `0x0000000D`:

```
DBPF header + index
└── 0x0000000D SaveGameData
    ├── 1  guid
    ├── 2  save_slot       (slot name, timestamps, active household)
    ├── 3  account
    ├── 4  neighborhoods
    ├── 5  households       (HouseholdData)
    ├── 6  sims             (SimData)
    ├── 7  zones
    └── 14 gameplay_data
```

Each `SimData` contains the full state:

| Field | Meaning |
| --- | --- |
| 1 | `sim_id` |
| 4 | `household_id` |
| 5/6 | first / last name |
| 7 | gender (`4096` male, `8192` female) |
| 8 | age (`1` baby, `2` toddler, `4` child, `8` teen, `16` young adult, `32` adult, `64` elder, `128` infant) |
| 15 | `significant_other` (spouse) |
| 23 | `nucleus_id` (save-specific ID) |
| 30 | `PersistableSimInfoAttributes` |
| 34 | `primary_aspiration` — an **aspiration track** ID |
| 47 | `GameplaySimData` (milestones, whims, favorites, …) |
| 60 | `extended_species` (`1` human, `2` dog, `3` cat, `4` small dog, `5` fox, `6` horse) |
| 68 | `fiance` |

`PersistableSimInfoAttributes` carries the trackers:

| Field | Tracker |
| --- | --- |
| 1 | relationships |
| 6 | event data (aspiration milestones/objectives) |
| 7 | death |
| 8 | pregnancy |
| 10 | traits (including preference traits) |
| 12 | careers |
| 13 | skills |
| 14 | genealogy |
| 17 | occult |
| 29 | favorites |
| 30 | degrees |
| 33 | trait statistics |

### Read data

- **Identity:** name, age, gender, species, occult flags, household, zone/world.
- **Traits / likes / dislikes:** the trait tracker holds personality traits, hidden
  traits, and preference traits. The SDK splits them into `traits` and
  `preferences` and reports unknown/modded IDs separately.
- **Aspiration:** the primary aspiration **track** is resolved (e.g.
  `Track_Popularity_C` → “Party Animal”). The exact aspiration inside the track
  is only present when the save stores it in the event data tracker.
- **Career:** career, branch/track, level title, pay, performance. The
  `track_level` field is a 0-based index into `CareerTrack.level_ids`;
  `user_display_level` is the level shown in-game.
- **Skills:** statistic/skill IDs with raw values and resolved tuning names.
- **Family:** `genealogy_tracker.family_relations` gives parents/grandparents/etc.
  The SDK adds reverse links (children) and derives siblings from shared parents.
- **Spouse/fiancé:** from `significant_other` / `fiance`.
- **Milestones:** developmental milestones from `GameplaySimData`, plus completed
  aspiration objectives/milestones from the event tracker.
- **Pregnancy, occult, degrees, death, statistics, favorites.**
- **Relationships:** per-Sim relationship tracker entries are exposed when the
  save contains them (bits, track values, target names).

### Current limitation

Older saves may store friendship/romance relationship services in the legacy
type-`0x00000006` “LDNB” persistence chunks rather than in `SaveGameData`. Those
chunks are not decoded yet. Such saves still expose spouse, family, traits,
careers, skills, milestones, and all other per-Sim data.

The *initial* friendship/romance values are not authored per save; they come from
tuning (`DefaultRelationshipInHousehold.RelationshipSetupMap` and
`PremadeSimRelationships.RELATIONSHIP_MAP`) and are exposed statically through
`Catalog.relationship_defaults`, `Catalog.premade_relationships` and
`HouseholdRelationship.friendship` / `.romance`. The save only records how those
values have changed through play. See
[`binary-formats.md`](binary-formats.md#module-level-tuning-blocks-and-initial-relationship-values).

## Tray files

| File | Contents |
| --- | --- |
| `.trayitem` | 8-byte header (`uint32 version`, `uint32 length`) + `TrayItem` protobuf: item ID, title, description, creator, timestamp, tags |
| `.householdbinary` | 16-byte header + `FamilyData` protobuf: `AccountFamilyData` with family name, money, description, and a list of `SimData` |
| `.sgi` / `.hhi` | appearance/thumbnail data (not parsed yet) |

`.trayitem` and `.householdbinary` files are paired by the shared ID after `!` in
their filenames. A Tray household reuses the same `SavedSim` model as saves, so
traits, likes/dislikes, careers, skills, genealogy, and pregnancy work identically.

## Validation

| Check | Result |
| --- | --- |
| Save files parsed | 6 (`Slot_…save` + `ver0`–`ver4`), 0 failures |
| Tray `.trayitem` files | 286, 0 failures |
| Tray `.householdbinary` files | 286, 0 failures |
| Example save | 59 Sims, 32 households, 59 zones |
| Example Tray library | 286 items + 286 households |

Bella Goth in the local save:

- Young Adult, Female, Human
- Traits: Family-Oriented, Good, Romantic
- Likes: Color Blue, Violin, Pop Music
- Aspiration track: Party Animal
- Career: Secret Agent / Intelligence Researcher (level 2, 19 §/hour)
- Skills: Charisma, Fitness, Programming
- Spouse: Mortimer Goth
- Children: Cassandra Goth, Alexander Goth
