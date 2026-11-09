"""Validate the SDK against The Sims Wiki.

Usage::

    python examples/validate_wiki.py
    python examples/validate_wiki.py --catalog-only
    python examples/validate_wiki.py --save "Slot_00000002.save" --limit-sims 50
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sims4_sdk import Sims4Workspace
from sims4_sdk.validation import WikiClient, run_validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default=".cache/wiki", help="wiki response cache")
    parser.add_argument("--limit-sims", type=int, default=50, help="pre-made Sim pages to fetch")
    parser.add_argument("--save", help="validate a specific save file")
    parser.add_argument("--no-save", action="store_true", help="compare pre-made static Sims instead of a save")
    parser.add_argument("--catalog-only", action="store_true", help="skip Sim comparisons")
    parser.add_argument("--include-mods", action="store_true", help="include mods in the catalog")
    parser.add_argument("--output", default="validation_report.md", help="Markdown report path")
    parser.add_argument("--json-output", default="validation_report.json", help="JSON report path")
    parser.add_argument("--refresh-catalog", action="store_true", help="ignore catalog cache")
    args = parser.parse_args()

    workspace = Sims4Workspace(include_mods=args.include_mods)
    static_data = workspace.static_data(refresh=args.refresh_catalog)
    print(static_data.summary())

    save = None
    if not args.catalog_only and not args.no_save:
        save_path = args.save or next(iter(workspace.save_files()), None)
        if save_path is not None:
            save = workspace.read_save(save_path, static_data.catalog)
            print(save.summary())
        elif args.save:
            print(f"save not found: {args.save}")
            return 1

    client = WikiClient(cache_dir=args.cache_dir)
    report = run_validation(
        static_data=static_data,
        client=client,
        sim_limit=args.limit_sims,
        save=save,
        catalog_only=args.catalog_only,
    )

    summary = report.summary()
    print(json.dumps(summary, indent=2))

    output = Path(args.output)
    output.write_text(report.to_markdown(), encoding="utf-8")
    print(f"wrote {output}")

    json_output = Path(args.json_output)
    json_output.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
