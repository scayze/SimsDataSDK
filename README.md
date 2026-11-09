# sims4-sdk

A Python SDK for reading **The Sims 4** data so it can be used by other tools:
game packages, DLC packages, mods, save files, and Tray files.

> Status: **Step 3 — saves and Tray files.** The SDK now reads the static catalog,
> pre-made Sims, live save-game state, and Tray/Gallery households. Save data
> includes traits, likes/dislikes, careers, skills, aspiration tracks, family
> relationships, milestones, pregnancy, occult state, and more.

## Quick start (no save file required)

```python
from sims4_sdk import Sims4Workspace

ws = Sims4Workspace()                 # auto-detects the game + user folder
catalog = ws.catalog                  # built once, then cached

print(catalog.summary())

# Catalog lookups
print(catalog.trait("trait_Mean"))    # Trait('trait_Mean', type='PERSONALITY')
print(catalog.trait("trait_Mean").display_name)   # "Mean"
print(catalog.preference("trait_SimPreference_Likes_Music_HipHop").preference_type)

# Every pre-made Sim that ships with the installed packs
for sim in ws.premade_sims():
    print(sim.full_name, [trait.display_name for trait in sim.personality_traits])
    print("  household:", sim.household_name)
    print("  aspiration:", sim.aspiration.display_name if sim.aspiration else None)

bella = ws.find_sim("Bella Goth")
goth = ws.find_household("premadeHouseholdTemplate_Goth")

# Live save data
save = ws.read_save(ws.save_files()[0])
bella_in_save = save.sim("Bella Goth")
print(bella_in_save.age, bella_in_save.gender, bella_in_save.species)
print([t.display_name for t in bella_in_save.personality_traits])
print(bella_in_save.career.title, bella_in_save.career.pay_per_hour)
print(bella_in_save.spouse_name, [child.name for child in bella_in_save.children])

# Gallery / Tray households
tray = ws.tray_library()
for household in tray.households:
    print(household.family_name, [sim.full_name for sim in household.sims])
```

Calls are cached under `%LOCALAPPDATA%\sims4-sdk\cache`; deleting that folder
forces a rebuild. Pass `cache_dir=...` to `Sims4Workspace` to use another folder.

## What works today

### Static catalog (Step 2)

- **Traits** — type (`PERSONALITY`, `GHOST`, `FEAR`, `WALKSTYLE`, …), display
  name, description, ages, species, conflicting traits, icon, source pack.
- **Preferences** — likes, dislikes, and no-opinion preferences.
- **Aspirations**, aspiration tracks, and categories.
- **Careers**, career tracks/branches, and career levels (titles, pay, schedule).
- **Milestones** — including the Growing Together developmental milestones.
- **Relationship bits**.
- **Pre-made Sims** — names, traits, likes/dislikes baked into SimInfo, skills,
  explicit aspiration/career level, dynasty, occult, household membership.
- **Pre-made households** — members and spouse/family relationships.
- **Pre-made ancestors** — names, gender, death traits, thumbnails.

### Saves and Tray (Step 3)

- **Save metadata** — slot name, timestamps, active household, account, version.
- **Live Sims** — age, gender, species, occult, traits, likes/dislikes, skills,
  careers, aspiration track, pregnancy, degrees, death, statistics, favorites.
- **Family** — spouse/fiancé, parents, children, siblings, grandparents and other
  genealogy relations.
- **Milestones** — developmental milestones and completed aspiration objectives.
- **Relationships** — per-Sim relationship tracker entries when present (bits,
  friendship/romance tracks, target names).
- **Households and zones** — members, funds, home zone, premade template IDs.
- **Tray/Gallery** — `.trayitem` metadata plus full Sims from `.householdbinary`,
  using the same `SavedSim` model.

See [`docs/save-and-tray.md`](docs/save-and-tray.md) for the protobuf field map,
validation numbers, and current limitations.

### Low-level binary readers (Step 1)

```python
from sims4_sdk.core import DBPF, StringTable, CombinedTuning

with DBPF(r"Data/Client/Strings_ENG_US.package") as package:
    for entry in package.iter_entries(type_id=StringTable.TYPE_ID):
        table = StringTable.parse(package.read_resource(entry))
        print(len(table), "strings")

    for entry in package.iter_entries(type_id=CombinedTuning.TYPE_ID):
        tuning = CombinedTuning.parse(package.read_resource(entry))
        for item in tuning.by_class("Trait")[:5]:
            print(item.name, item.instance_id)
```

Low-level helpers are also public:

- `sims4_sdk.core.refpack` — EA RefPack (QFS) decompression.
- `sims4_sdk.core.stbl` — localized string tables.
- `sims4_sdk.core.data_tables` — the binary `DATA` table format.
- `sims4_sdk.core.simdata` — SimData (`0x545AC67A`) resources.
- `sims4_sdk.core.fnv` — FNV-1 / FNV-1a hashing used by tuning IDs and STBL keys.
- `sims4_sdk.siminfo` — partial SimInfo reader (baked trait lists).

## Layout

```
src/sims4_sdk/
├── core/               # low-level binary readers
│   ├── dbpf.py
│   ├── refpack.py
│   ├── stbl.py
│   ├── data_tables.py
│   ├── combined_tuning.py
│   ├── simdata.py
│   ├── resource_types.py
│   └── fnv.py
├── catalog/            # save-independent extraction
│   ├── models.py       # Trait, Preference, Aspiration, Career, Milestone, ...
│   ├── builder.py      # tuning scan + catalog extraction
│   ├── strings.py      # merged STBL resolution
│   ├── premades.py     # PremadeSimTemplate / household / ancestor extraction
│   └── static.py       # coordinated build + cache
├── save/               # live save and Tray data
│   ├── protobuf.py     # schema-driven protobuf decoder
│   ├── schema.py       # SaveGameData / SimData / FamilyData / TrayItem schemas
│   ├── models.py       # SaveFile, SavedSim, SavedHousehold, TrayHousehold, ...
│   ├── reader.py       # .save reader
│   └── tray.py         # .trayitem / .householdbinary reader
├── installation.py     # package discovery and load order
├── siminfo.py          # SimInfo trait-list reader
├── workspace.py        # Sims4Workspace facade
└── paths.py            # install / user directory discovery
tests/                  # unit tests + optional local integration tests
examples/
```

## Roadmap

1. **Step 1 — binary foundation** (done).
2. **Step 2 — static catalog + pre-made Sims** (done; save-independent).
3. **Step 3 — saves and Tray files** (done; live Sim state, family, milestones,
   careers, skills, pregnancy, occult).
4. **Step 4 — Sims Wiki validation** (catalog and pre-made/played Sim reconciliation).
5. **Step 5 — public API/export tooling** (CLI, JSON/SQLite/Polars helpers).

> Note on pre-made Sim values: where the game bakes values into the SimInfo
> resource (for example randomized traits), those values are surfaced. Where the
> game only assigns a value at runtime (some base-game aspirations/careers), the
> template value is exposed when present and `None` otherwise.


## Installation

```bash
pip install -e ".[dev]"
```

Python 3.10+ is required. The core readers use only the standard library.

## Testing

```bash
python -m pytest                              # unit tests
python -m pytest -m "integration and not slow" # fast local integration tests
python -m pytest -m "integration"             # all local integration tests
SIMS4_FULL_TEST=1 python -m pytest -m "integration"  # scan every installed pack
```

Tests that require a real installation are marked `integration` and are skipped
automatically when no Sims 4 install is found. Set `SIMS4_INSTALL_DIR` and
`SIMS4_USER_DIR` to point at a specific installation/user folder. Full catalog
builds are cached, so the first run is the slow one.

### Verified against the local installation

| Check | Result |
| --- | --- |
| `SimulationDeltaBuild0.package` | DBPF 2.1, 135,336 entries |
| `Strings_ENG_US.package` | STBL v5, 58,419 strings |
| Full-build Combined Tuning | XML, `Trait` entries present |
| EP13 delta Combined Tuning | binary `DATA`, 4,749 entries |
| EP13 `DevelopmentalMilestone` | 109 entries |
| Save file | constant-group index, JPEG + RefPack resources |
| Full game scan | 629 packages, 2,581,974 index entries, 0 failures |
| All English string tables | 117 packages, 163,302 strings, 0 failures |
| Node test set (base + EP13) | 745 traits, 166 preferences, 191 aspirations, 223 career levels, 109 milestones, 36 pre-made Sims, 15 households, 21 ancestors, 0 errors |
| Full static scan (base + all packs + mods) | 2,795 traits, 334 preferences, 392 aspirations, 146 careers, 671 career levels, 201 milestones, 766 relationship bits, 400 pre-made Sims, 191 households, 41 ancestors, 0 errors, 616 packages; ~255 s first build, cached afterwards |
| Save files | 6 parsed (`Slot_*` + `ver0`–`ver4`), 0 failures; example save: 59 Sims / 32 households / 59 zones |
| Tray files | 286 `.trayitem` + 286 `.householdbinary`, 0 failures |

See [`docs/binary-formats.md`](docs/binary-formats.md) for the verified format
notes, and run the example:

```bash
python examples/inspect_package.py "path/to/SimulationDeltaBuild0.package"
```

