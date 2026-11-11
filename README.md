# sims4-sdk

A Python SDK for reading **The Sims 4** data so it can be used by other tools:
game packages, DLC packages, mods, save files, and Tray files.

The SDK reads game data and can serialize its models to JSON. It does not write
game packages, saves, Tray files, or script mods; an exporter can consume the
SDK's models without changing the original game files.

> Status: **Step 5 — public library API.** The SDK is now designed to be
> embedded in other Python projects: every model serializes to JSON-safe
> dictionaries, catalog and save lookups accept IDs *or* names, static data can
> be saved as a portable snapshot and reopened on a machine without the game,
> and all SDK errors share one base class.

Package discovery includes the base Simulation and Client folders, pack-root
packages and `Delta/<PACK>` packages, followed by optional mods. Scanning all
client packages can take longer and use more memory than older SDK releases.
Tray library scans collect per-file failures in `library.errors`.

Static builds retain starter household and lot records in `static.world` and
report recoverable extraction failures in `static.catalog.diagnostics`. See
[static catalog sources and diagnostics](docs/static-catalog.md#tuning-sources).

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

# Base-game households that have no tuning template
bff = ws.find_household("BFF")
print(bff.funds, [member.full_name for member in bff.members])
for lot in ws.lots():
    print(lot.lot_name, "->", lot.household_name)

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
- **Pre-made households** - members, funds and spouse/family relationships.
- **Gender options / preferences** - frame, clothing, toilet use, lactation,
  attraction and WooHoo interests, exploring status and impregnation, derived from
  the `trait_GenderOptions_*` / `trait_SexualOrientation_*` traits.
- **Starter-save households** - the older-pack pre-mades that have no tuning
  template (BFF, Pancakes, Caliente, Roomies, Spencer-Kim-Lewis, …), including
  funds, gender, age, aspiration track, career **and starting level**, raw skill
  values, spouse and parent/grandparent genealogy.
- **Initial relationship values** - household defaults (Roommate 15, Family 45,
  Spouse romance 75), cross-household pairs from `PremadeSimRelationships`, and
  the value interval of relationship bits.
- **Steady / fiancé / marriage bits** - the bit IDs the engine uses for steady,
  engaged and married states, plus the family/romance trope ID lists
  (`Catalog.steady_bit_id`, `.engagement_bit_id`, `.marriage_bit_id`,
  `.family_trope_ids`, `.romance_trope_ids`).
- **Lots** — lot names/descriptions and the pre-made household occupying them.
- **Pre-made ancestors** — names, gender, death traits, thumbnails.

### Saves and Tray (Step 3)

- **Save metadata** — slot name, timestamps, active household, account, version.
- **Live Sims** — age, gender, species, occult, traits, likes/dislikes, skills,
  careers, aspiration track, pregnancy, degrees, death, statistics, favorites.
- **Family** - spouse/fiancé/steady, parents, children, siblings, grandparents
  and other genealogy relations, including family/romance relationship tropes.
- **Gender options / preferences** - same `GenderOptions` view as static Sims.
- **Milestones** - developmental milestones and completed aspiration objectives.
- **Relationships** - per-Sim relationship tracker entries when present (bits,
  friendship/romance tracks, target names). Steady partner IDs are supplemented
  with the steady relationship bit when available.
- **Artwork** — save thumbnails, Tray household images and Sim portraits,
  including separately accessible embedded alpha masks. See
  [Saves and Tray artwork](docs/save-and-tray.md#artwork).
- **Households and zones** — members, funds, home zone, premade template IDs.
- **Tray/Gallery** — `.trayitem` metadata plus full Sims from `.householdbinary`,
  using the same `SavedSim` model.

See [`docs/save-and-tray.md`](docs/save-and-tray.md) for the protobuf field map,
validation numbers, and current limitations.

### Sims Wiki validation (Step 4)

- **Cached MediaWiki client** — `sims.fandom.com/api.php`, with disk caching and
  batch page fetching.
- **Wikitext parsers** — `Infobox Sim4`, skill tables, relationship tables, trait
  tables, aspiration tables, career tables, milestone tables, and likes/dislikes
  tables.
- **Catalog coverage** — reports matched/missing SDK entries per domain.
- **Sim reconciliation** — compares age, gender, traits, aspiration, career,
  spouse, children, parents, skills, and relationships.
- **Reports** — Markdown and JSON, with per-field status
  (`match`, `mismatch`, `missing_sdk`, `missing_wiki`, `not_available`).

```bash
pip install -e ".[validation]"
python examples/validate_wiki.py                # first save, 50 Sim pages
python examples/validate_wiki.py --catalog-only
python examples/validate_wiki.py --no-save      # compare static pre-made Sims
```

Or from Python:

```python
report = ws.validate_wiki(sim_limit=25)
print(report.summary())
print(report.to_markdown()[:2000])
```

See [`docs/wiki-validation.md`](docs/wiki-validation.md) for methodology,
results, and known gaps.

### Portable library API (Step 5)

The SDK is library-first: no external data tooling is required at runtime, and
every public model can be handed to another Python application or written to
JSON.

**Serialization.** Every model has `to_dict()` and `to_json()`:

```python
save = ws.read_save(ws.save_files()[0])

save.to_dict()                      # JSON-safe dict, raw payloads excluded
save.to_json("save.json")           # pretty JSON on disk
ws.catalog.to_json("catalog.json")  # traits, careers, milestones, ...
ws.static_data().to_dict()          # catalog + pre-mades in one document

# Opt in to data that is omitted by default
ws.static_data().to_dict(include_strings=True)       # catalog STBL table
ws.catalog.to_dict(include_tuning_index=True)        # every tuning ID → name
save.to_dict(include_raw=True)                       # decoded protobuf payloads
```

The output is plain JSON: `Path` becomes a string, `bytes` becomes lowercase
hex, resource keys become `TTTTTTTT!GGGGGGGG!IIIIIIIIIIIIIIII`, computed
properties (`full_name`, `age`, `gender_options`, `personality_traits`,
`likes`, …) are included, and references to catalog definitions are emitted as
compact `{id, name, display_name}` objects rather than duplicating the catalog.
`sims4_sdk.to_dict()` / `to_json()` accept any model or nested structure, and
`Sims4JSONEncoder` plugs into `json.dumps`.

**Name lookups and filters.** Catalog and save accessors accept IDs or names,
try an exact match first, and then fall back to case-insensitive matching.
`find_*` methods do substring filtering:

```python
catalog.trait("TRAIT_MEAN")          # exact name, case-insensitive fallback
catalog.career_track("career_criminal")
catalog.tuning_name(123456)          # arbitrary tuning ID → name

catalog.find_traits("vampire", trait_type="OCCULT", pack="EP01")
catalog.find_preferences(preference_type="DISLIKE")
catalog.find_careers(pack="BASE")
catalog.packs()                      # packs represented in the catalog

save.sim("Bella Goth")               # exact, then fragment
save.household_sims("Goth")
save.find_sims(age="ADULT", occult="VAMPIRE")
tray.find_households(creator="Maxis")
```

**Portable snapshots.** A catalog or the complete static data can be pickled
once and reopened without an installation:

```python
from sims4_sdk.catalog import Catalog

ws.save_static("sims4-static.pkl")   # catalog + pre-made Sims/households/lots

offline = Sims4Workspace.from_static(
    "sims4-static.pkl",
    user_dir=r"C:\Users\me\Documents\Electronic Arts\The Sims 4",
)
save = offline.read_save(offline.latest_save_path())

# Or just the catalog
ws.catalog.save("catalog.pkl")
catalog = Catalog.load("catalog.pkl")
```

Snapshots are trusted local artifacts produced by the SDK; use `to_dict()` /
`to_json()` when another program needs to consume the data. Reading a Tray
folder or a save only needs the catalog, so `from_static` works for archives and
CI without the game installed.

**Unified exceptions.** Every SDK-specific error subclasses
`sims4_sdk.Sims4SDKError`, while keeping its historical builtin base:

```python
from sims4_sdk import Sims4SDKError

try:
    save = ws.read_save(path)
except Sims4SDKError as exc:
    ...
```

`ValueError` and `RuntimeError` handlers written against earlier versions keep
working. Snapshot failures raise `CatalogError` / `StaticDataError`.

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
│   ├── worlds.py       # lot manifest + starter-save household resources
│   └── static.py       # coordinated build + cache
├── save/               # live save and Tray data
│   ├── protobuf.py     # schema-driven protobuf decoder
│   ├── schema.py       # SaveGameData / SimData / FamilyData / TrayItem schemas
│   ├── models.py       # SaveFile, SavedSim, SavedHousehold, TrayHousehold, ...
│   ├── reader.py       # .save reader
│   └── tray.py         # .trayitem / .householdbinary reader
├── validation/         # Sims Wiki validation
│   ├── wiki_client.py  # cached MediaWiki API client
│   ├── parse.py        # infobox/table/wikitext parsers
│   ├── reconcile.py    # field-by-field comparison
│   ├── validator.py    # orchestration
│   └── models.py       # report/comparison models
├── installation.py     # package discovery and load order
├── siminfo.py          # SimInfo trait-list reader
├── export.py           # to_dict / to_json serialization
├── exceptions.py       # Sims4SDKError base class
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
4. **Step 4 — Sims Wiki validation** (done; catalog, pre-made/played Sim
   reconciliation, Markdown/JSON reports).
5. **Step 5 — public library API** (done; model serialization, name/ID lookups
   and filters, portable static snapshots, `Sims4Workspace.from_static`, unified
   exceptions).

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

## Performance

A cold full scan (602 packages, 2.58M index entries, ~300 MB of tuning data)
takes roughly **7 seconds** on a 6-core desktop CPU; the cached load afterwards
is immediate.  The hot path is built around four ideas:

- **One index pass.** Package indexes are read in one block and scanned in
  place; only the entries whose resource type is actually needed are turned
  into `ResourceEntry` objects.
- **No XML detour.** Binary Combined Tuning blobs are decoded straight from the
  seven `DATA` tables into an `ElementTree`. Round-tripping through a ~200 MB
  XML string used to be about two thirds of the whole build.
- **Lazy subtrees.** Tuning entries, the shared `<g>` value table and the `<M>`
  tuning modules are built on first access, so only the few thousand entries a
  catalog build actually reads are ever materialised. `CombinedTuning.root`
  materialises everything if you ask for it.
- **Fused resource collection.** Strings, tuning, world resources and the
  SimInfo index are gathered in a single pass per package, so pre-made Sim
  extraction never re-opens the installation.

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
| Full static scan (base + all packs, no mods) | 2,795 traits, 334 preferences, 392 aspirations, 146 careers, 671 career levels, 201 milestones, 766 relationship bits, 431 pre-made Sims, 204 households, 41 ancestors, 548 lots, 16 relationship defaults, 348 premade relationship pairs, 25 bit ranges, 0 errors, 602 packages; ~7 s first build, cached afterwards |
| Starter-save households | BFF (9,000), Pancakes (20,000), Roomies (14,000), Spencer-Kim-Lewis (55,500), Caliente (28,500); 0 parse errors |
| Initial relationships | Pancakes spouse 45/75; Caliente parent/child 45/0; Megumi ↔ Kado 10/-60; Megumi ↔ Sachiko 60; Bjergsen spouse romance range 25–75 |
| Save files | 6 parsed (`Slot_*` + `ver0`–`ver4`), 0 failures; example save: 59 Sims / 32 households / 59 zones |
| Tray files | 286 `.trayitem` + 286 `.householdbinary`, 0 failures |
| Wiki catalog coverage | traits 99.6%, preferences 97.6%, aspirations 99.1%, careers 100%, milestones 100% |
| Wiki save validation | Bella Goth 100% field match (age, gender, traits, aspiration, career, spouse, children, skills) |

See [`docs/binary-formats.md`](docs/binary-formats.md) for the verified format
notes, and run the example:

```bash
python examples/inspect_package.py "path/to/SimulationDeltaBuild0.package"
```

