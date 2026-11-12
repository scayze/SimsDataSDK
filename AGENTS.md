# AGENTS.md — sims4-sdk

Python SDK (3.10+, stdlib-only core) for reading Sims 4 packages, saves, Tray files. Read-only: never write game files.

## Layout
- `src/sims4_sdk/core/` — DBPF, tuning, STBL, SimData binary readers
- `src/sims4_sdk/catalog/` — static catalog, premades, worlds
- `src/sims4_sdk/save/` — save/Tray protobuf + models
- `src/sims4_sdk/validation/` — Sims Wiki checks
- `workspace.py` — main facade (`Sims4Workspace`); `export.py` — `to_dict`/`to_json`; `exceptions.py` — `Sims4SDKError`

## Setup / Test
```bash
pip install -e ".[dev]"
python -m pytest                              # unit only
python -m pytest -m "integration and not slow" # fast local (needs game)
SIMS4_INSTALL_DIR=... SIMS4_USER_DIR=... python -m pytest -m "integration"
```
`pythonpath=["src"]` set in pyproject. Integration tests auto-skip without a game install.

## Rules
- Treat the repo as yours: keep it clean. Disagree or propose an alternative when a request would worsen it.
- New models: add `to_dict()`-compatible fields (JSON-safe: `str`/`hex`/`ResourceKey` format), keep `to_json()` working.
- Lookups accept ID or name with case-insensitive fallback; `find_*` = substring filter.
- Raise `Sims4SDKError` subclasses (keep builtin base for compat).
- Core readers: stdlib only, no new deps without need.
- Prefer editing existing files; verify with `pytest` + `python examples/inspect_package.py <pkg>` when touching binary parsing.
