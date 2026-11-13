# Skill curves from tuning

`discover_skill_curves` reads the shared level-type table from game and mod
tuning in SDK package order. It interprets the table's per-level XP amounts as
successive increments and uses their cumulative sums as inclusive thresholds.
For example, the observed base-game `MAJOR` values begin with 100 and 1440,
so its first two thresholds are 100 and 1540 XP.

```python
from sims4_sdk import Sims4Workspace
from sims4_sdk.skill_discovery import discover_skill_curves
from sims4_sdk.skills import convert_skill_xp

ws = Sims4Workspace(include_mods=True)
curves = discover_skill_curves(ws.installation.packages)
definition = ws.catalog.statistic(16699)  # Charisma, if installed
curve = curves.for_skill(definition)
progress = convert_skill_xp(1540, curve)  # raw XP is always retained
print(progress.level, progress.assigned, progress.status)
for issue in curves.diagnostics:
    print(issue.stage, issue.package_path, issue.resource_key, issue.message)
```

The definition must be explicitly recognized as a skill and specify a
`skill_level_type` present in the table. Unknown types and missing definitions
remain unresolved. Assignment is also independent: pass `assigned=True` or
`False` only when the source establishes it; a 100-XP value alone does not.
Thresholds below the first level remain unresolved, and values above the final
threshold are capped by `convert_skill_xp`.

When several resources define the shared table, the last table in the SDK's
ordered packages wins; combined tuning follows individual tuning within each
package. This deterministic policy is not a guarantee of the game's mod load
order. A table replaces the entire previous table rather than merging rows.
`package_path` and `resource_key` identify the winning table. Scan failures
make `complete` false, and `for_skill` returns no curve by default because a
later override may have been missed. `allow_incomplete=True` opts into the
best table found; inspect diagnostics before relying on it. Re-run discovery
when packages change. `complete=True` means supported resource reads succeeded,
not that all possible overrides were detected: discovery reads the SDK's
combined-tuning and standard tuning resource types, but does not scan other
class-hashed mod resources. Those and script mods can alter runtime behavior
beyond what this reader can determine.
