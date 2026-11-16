# sims4-sdk

Python SDK for reading The Sims 4 packages, game data, saves, and Tray files.
The SDK does not modify game files. Python 3.10+ and Pillow are required.

## Installation

```bash
pip install .
# For development and tests:
pip install -e ".[dev]"
# For Sims Wiki validation:
pip install ".[validation]"
```

## Quick start

```python
from sims4_sdk import Sims4Workspace

ws = Sims4Workspace()  # Detects the game and user data folders
catalog = ws.catalog   # Builds static data on first use

trait = catalog.trait("trait_Mean")
if trait:
    print(trait.display_name)

for sim in ws.premade_sims():
    print(sim.full_name, sim.household_name)

save = ws.latest_save()
if save:
    bella = save.sim("Bella Goth")
    if bella:
        print(bella.full_name, bella.age)

for household in ws.tray_library().households:
    print(household.family_name)
```

Pass `install_dir` and `user_dir` to `Sims4Workspace`, or set
`SIMS4_INSTALL_DIR` and `SIMS4_USER_DIR`, to select specific folders. The SDK
scans installed packages and, by default, mods; pass `include_mods=False` to
exclude mods. Static data is cached under `%LOCALAPPDATA%\sims4-sdk\cache` by
default; pass `cache_dir` to change it. Extraction issues are available in
`ws.catalog.diagnostics`, and Tray scan errors in `ws.tray_library().errors`.

## Data and serialization

The SDK separates source extraction from interpretation. Extraction exposes
supported decoded fields and their source; resolution links records, resolves
names, and derives convenience values. The workspace's usual `read_save()` and
`static_data()` methods perform both stages. Use the stages directly when you
need to inspect the evidence or apply your own rules:

```python
source = ws.extract_save(ws.latest_save_path())
print(source.sims)                 # schema-selected protobuf fields
save = ws.resolve_save(source)     # linked and derived view

static_source = ws.extract_static()
print(static_source.collected.entries)  # selected tuning entries and sources
static = ws.resolve_static(static_source)
```

Resolution does not change the source's semantic data. Save source fields are
schema-selected, not a lossless protobuf representation; unknown fields are
skipped. For a file-backed save, `source.path` and `source.resource_key` locate
the original bytes through `DBPF`. Static extraction covers supported resource
types and follows the SDK's package precedence; it does not extract every game
resource. Inspect diagnostics for failures and unsupported data.

The catalog includes traits, preferences, aspirations, careers, milestones,
relationships, pre-made Sims, households and lots. Save and Tray readers expose
Sims, households, relationships, skills and artwork. See the
[static catalog](docs/static-catalog.md) and [save and Tray](docs/save-and-tray.md)
guides for details and limitations.

Models support `to_dict()` and `to_json()`; the top-level functions also accept
nested structures. Lookups accept IDs or names, with case-insensitive fallback;
`find_*` methods filter results.

```python
catalog.to_json("catalog.json")
ws.static_data().to_dict(include_strings=True)
ws.save_static("static.pkl")
offline = Sims4Workspace.from_static("static.pkl", user_dir="path/to/The Sims 4")
```

Snapshots use Python pickle. **Load only trusted snapshots:** unpickling can
execute arbitrary code. Catalog and static snapshots are versioned; unsupported versions
must be rebuilt. Use JSON for interchange with other programs.

SDK-specific exceptions derive from `sims4_sdk.Sims4SDKError`. Filesystem and
other standard Python errors may also be raised.

## Binary readers and validation

`sims4_sdk.core` provides DBPF, string table, tuning, SimData, image and RefPack
readers. See [binary formats](docs/binary-formats.md) and
[examples/inspect_package.py](examples/inspect_package.py).

The optional [Sims Wiki validation](docs/wiki-validation.md) tools compare
catalog and Sim data with the wiki. Install the `validation` extra first.

## Tests

```bash
python -m pytest
python -m pytest -m "integration and not slow"
python -m pytest -m "integration"
```

Integration tests requiring a local game installation are skipped when it is not
available. Set `SIMS4_INSTALL_DIR` and `SIMS4_USER_DIR` to select the installation
and user folders.
