"""Extract explicitly typed statistic definitions from SimData DATA tables.

Only schema and table metadata are used for classification: no tuning-name or
printable-string heuristics. Unknown client fields remain unknown.
"""

from __future__ import annotations

from typing import Optional

from ..core.simdata import SimData
from .models import StatisticDefinition, TuningSource

# Retail statistic SimData group. Mod packages may use arbitrary groups.
STATISTIC_SIMDATA_GROUP = 0x009BC58E
STATISTIC_SCHEMAS = frozenset({"Skill", "TunableSkill", "Statistic"})


def statistic_from_simdata(data: bytes, instance: int, source: TuningSource) -> Optional[StatisticDefinition]:
    """Return a definition for a recognized one-row root table, else None.

    This does not claim that every Statistic is a skill, or interpret binary
    enum values whose meaning has not been established.
    """
    parsed = SimData.parse(data)
    candidates = [table for table in parsed.tables.tables
                  if table.name and table.row_count == 1 and
                  0 <= table.schema_index < len(parsed.tables.schemas) and
                  parsed.tables.schemas[table.schema_index].name in STATISTIC_SCHEMAS]
    if len(candidates) != 1:
        return None
    table = candidates[0]
    schema = parsed.tables.schemas[table.schema_index].name
    row = parsed.table(table.name)[1][0]
    key = row.get("stat_name")
    raw = f"0x{key:08X}" if isinstance(key, int) and key else None
    icon = row.get("icon")
    if isinstance(icon, dict) and all(isinstance(icon.get(k), int) for k in ("type", "group", "instance")):
        icon = f"{icon['type']:08X}:{icon['group']:08X}:{icon['instance']:016X}"
    else:
        icon = None
    level_type = row.get("skill_level_type")
    return StatisticDefinition(
        id=instance, name=table.name, tuning_class=schema,
        is_skill=True if schema in {"Skill", "TunableSkill"} else None,
        display_name=None, display_name_raw=raw,
        display_name_field="stat_name" if raw is not None else None,
        icon=icon, source=source,
        skill_level_type_raw=level_type if isinstance(level_type, int) else None,
    )
