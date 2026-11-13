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
- **Spouse/fiancé/steady:** spouse and fiancé come from `significant_other` /
  `fiance`; a steady partner is not stored separately, so the SDK derives it from
  the `STEADY_RELATIONSHIP_BIT` in the relationship bits. Missing spouse/fiancé
  links are also recovered from the marriage/engagement bits.
- **Family and romance dynamics:** `genealogy_tracker.relationship_tropes` is
  decoded into `SavedSim.tropes` (`kind` is `FAMILY` or `ROMANCE`, with the
  relationship-bit display name).
- **Gender options / preferences:** the `trait_GenderOptions_*` and
  `trait_SexualOrientation_*` traits are exposed as
  `SavedSim.gender_options` (frame, clothing, toilet use, lactation, attraction,
  WooHoo interests, exploring status, impregnation). These traits are part of the
  normal trait tracker, so they are also present in `traits`.
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
| `.sgi` / `.hhi` | Sim portraits and household image variants |

`.trayitem` and `.householdbinary` files are paired by the shared ID after `!` in
their filenames. A Tray household reuses the same `SavedSim` model as saves, so
traits, likes/dislikes, careers, skills, genealogy, and pregnancy work identically.
`read_tray_library()` continues after a per-file error. Inspect `library.errors`
for dictionaries with `path` and `error` strings; the same diagnostics are
included in `library.to_dict()`. Direct single-file readers still raise errors.

For a file-oriented view, `sims4_sdk.save.list_tray_households(folder)` returns
groups with the household and item paths, decoded data, image paths, and latest
file modification time. Incomplete groups remain visible. Duplicate household
or item files sharing an identifier are reported as ambiguous and are not
selected for decoding. Household images are matched by household identifier;
Sim portraits are matched by decoded Sim ID. Unmatched or ambiguous images are
retained in `unmatched_images`, and errors in `errors`. This avoids loading a
catalog or decoding image bytes, but still decodes full household protobufs; it
is not a names-only parser. Tray item text is not assigned as an aspiration to
a Sim based on proximity.

## Artwork

`decode_artwork(data)` and `read_tray_image(path)` reject JPEGs without an end
marker by default. Pass `tolerate_missing_end=True` to retain a structurally
parsed image scan without that marker; the returned `Artwork` preserves the
bytes and sets `missing_end_marker`. This does not validate JPEG pixel data or
repair truncated segments, and PNG conversion may still fail.

Save thumbnails and lot artwork are read from the save package's image
resources and exposed as `save.artwork`, keyed by their complete `ResourceKey`.
`save.thumbnail_image` returns the instance-zero household thumbnail, and
`save.thumbnail` returns its JPEG bytes. `save.household_artwork` includes only
household-thumbnail instances that match an actual household ID; the
instance-zero thumbnail is not assumed to belong to a particular household.
Individual image errors appear in `save.artwork_errors` and do not prevent the
save from loading. A `read_save_resource()` payload has no package artwork.

Tray images are read lazily, so opening a large library does not load every
image into memory:

```python
household = library.households[0]
cover = household.household_image()        # largest matching .hhi variant, or None
portrait = household.portrait(household.sims[0].sim_id)  # .sgi, or None
if cover:
    jpeg_bytes = cover.jpeg
    mask_bytes = cover.alpha_mask         # PNG/JPEG bytes, or None
  png_bytes = cover.to_png()            # PNG with the alpha mask applied
```

`household.household_images()` returns all matching variants, and
`read_tray_image(path)` reads a standalone `.hhi` or `.sgi`. Each `Artwork`
contains the JPEG, optional alpha image and format, and image dimensions. The
SDK recognizes unwrapped JPEGs and the version-2 obfuscated Tray wrapper;
unsupported or malformed image files raise `ArtworkError`. Alpha data can span
multiple `ALFX` continuation segments. The SDK also exposes the original image
and mask bytes separately. `to_png()` raises `ArtworkError` if their dimensions
do not match or their pixel data cannot be decoded.
The image data is omitted from a save's normal JSON export; call
`Artwork.to_dict()` or pass `include_raw=True` to include it as hex strings.

Starter household resources also expose relationships, developmental milestones,
fiancé and steady partner IDs, occult flags and the decoded degree tracker on
`StarterMember`. These use the same relationship and milestone models as saves.
Skill values remain raw XP: the SDK does not currently infer skill levels or
distinguish an unassigned skill's floor from a deliberately assigned skill.

For an explicit, shared conversion of raw values from starter, save, or Tray
data, use `sims4_sdk.skills.convert_skill_xp(value, curve, assigned=...)`.
`SkillCurve` accepts inclusive thresholds starting at level 1, and values above
the last threshold are capped. Without a curve the result preserves XP and has
`status="unresolved_curve"`; assignment defaults to unknown and a known
unassigned value has no displayed level. A 100 XP value alone does not prove
assignment. The optional adult, child, toddler, and vampire-lore reference
curves are historical studio estimates calibrated against observed starter XP,
not thresholds extracted from game tuning. Select them only when the caller has
evidence that they apply; skill names are not used to select a curve. Custom
curves can be supplied with their source. Automatic game/mod curve discovery and
assignment detection are not implemented.

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
