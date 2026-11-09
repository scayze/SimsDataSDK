# sims4-sdk

A Python SDK for reading **The Sims 4** data so it can be used by other tools:
game packages, DLC packages, mods, save files, and Tray files.

> Status: **Step 1 — binary foundation.** The package currently ships the low-level
> readers (DBPF, RefPack, STBL, DATA tables, Combined Tuning, SimData). Higher-level
> domain extraction (traits, milestones, careers, relationships, …) lands in later steps.

## Installation

```bash
pip install -e ".[dev]"
```

Python 3.10+ is required. The core readers use only the standard library.

## What works today

```python
from sims4_sdk.core import DBPF, StringTable, CombinedTuning

with DBPF(r"Data/Client/Strings_ENG_US.package") as package:
    # Every STBL resource in the package
    for entry in package.iter_entries(type_id=StringTable.TYPE_ID):
        table = StringTable.parse(package.read_resource(entry))
        print(len(table), "strings")

    # Combined tuning (binary DATA or XML; both are handled)
    for entry in package.iter_entries(type_id=CombinedTuning.TYPE_ID):
        tuning = CombinedTuning.parse(package.read_resource(entry))
        print(len(tuning), "tuning entries")
        for item in tuning.by_class("Trait")[:5]:
            print(item.name, item.instance_id)
```

Low-level helpers are also public:

- `sims4_sdk.core.refpack` — EA RefPack (QFS) decompression.
- `sims4_sdk.core.stbl` — localized string tables.
- `sims4_sdk.core.data_tables` — the binary `DATA` table format.
- `sims4_sdk.core.simdata` — SimData (`0x545AC67A`) resources.
- `sims4_sdk.core.fnv` — FNV-1 / FNV-1a hashing used by tuning IDs and STBL keys.

## Layout

```
src/sims4_sdk/
├── core/               # low-level binary readers
│   ├── dbpf.py         # DBPF 2.x container + index reader
│   ├── refpack.py      # RefPack (QFS) decompressor
│   ├── stbl.py         # STBL string tables
│   ├── data_tables.py  # binary DATA table decoder
│   ├── combined_tuning.py
│   ├── simdata.py
│   ├── resource_types.py
│   └── fnv.py
└── paths.py            # install / user directory discovery
tests/                  # unit tests + optional local integration tests
```

## Testing

```bash
python -m pytest                      # unit tests
python -m pytest -m integration       # reads the local installation
```

Tests that require a real installation are marked `integration` and are skipped
automatically when no Sims 4 install is found. Set `SIMS4_INSTALL_DIR` and
`SIMS4_USER_DIR` to point at a specific installation/user folder.

The readers were verified against game files:

| Check | Result |
| --- | --- |
| `SimulationDeltaBuild0.package` | DBPF 2.1, 135,336 entries |
| `Strings_ENG_US.package` | STBL v5, 58,419 strings |
| Full-build Combined Tuning | XML, `Trait` entries present |
| EP13 delta Combined Tuning | binary `DATA`, 4,749 entries |
| EP13 `DevelopmentalMilestone` | 109 entries |
| Save file | constant-group index, JPEG + RefPack resources |

See [`docs/binary-formats.md`](docs/binary-formats.md) for the verified format
notes, and run the example:

```bash
python examples/inspect_package.py "path/to/SimulationDeltaBuild0.package"
```

