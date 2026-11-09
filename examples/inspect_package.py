"""Print a human-readable summary of a The Sims 4 package.

Usage::

    python examples/inspect_package.py "C:/path/to/Some.package"

This is intentionally small; it only demonstrates the Step 1 readers.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from sims4_sdk.core import (
    COMBINED_TUNING_TYPE_ID,
    STRING_TABLE_TYPE_ID,
    CombinedTuning,
    DBPF,
    StringTable,
    type_name,
)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <package>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    with DBPF(path) as package:
        header = package.header
        print(
            f"{path.name}: DBPF {header.major_version}.{header.minor_version}, "
            f"{len(package.entries)} entries, index flags 0x{package.index_flags:X}"
        )

        counts = Counter(entry.key.type_id for entry in package.entries)
        print("\nresource types:")
        for type_id, count in counts.most_common(25):
            print(f"  {type_id:08X} {count:>8}  {type_name(type_id)}")

        stbls = list(package.iter_entries(type_id=STRING_TABLE_TYPE_ID))
        if stbls:
            print("\nstring tables:")
            total = 0
            for entry in stbls:
                table = StringTable.parse(package.read_resource(entry))
                total += len(table)
                print(f"  {entry.key}: {len(table)} strings")
            print(f"  total: {total} strings")

        tunings = list(package.iter_entries(type_id=COMBINED_TUNING_TYPE_ID))
        if tunings:
            print("\ncombined tuning:")
            for entry in tunings:
                tuning = CombinedTuning.parse(package.read_resource(entry))
                classes = Counter(item.cls for item in tuning.entries)
                print(f"  {entry.key}: {len(tuning)} tuning entries")
                for name, count in classes.most_common(10):
                    print(f"    {name:<24} {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
