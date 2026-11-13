# SimData statistic definitions

The catalog can enumerate definitions found only in SimData as well as tuning
XML. It reads structured DATA tables with an explicit `Skill`, `TunableSkill`,
or `Statistic` schema; it does not classify names or printable strings. For
retail resources the scan is restricted to group `009BC58E`. Mod SimData can
use arbitrary groups, so it is considered independently of that group.

`catalog.statistic(id)` and `catalog.find_statistics()` return the same
`StatisticDefinition` model for both sources. SimData records contain the
table name, resource instance ID, source path and key, and where present a
localized `stat_name` key and icon. `skill_level_type_raw` preserves the
numeric SimData enum; `skill_level_type` and age restrictions remain unknown
unless explicitly extracted from XML. An unresolved string key is preserved
in `display_name_raw`, with `display_name` left null. The selected locale's
merged strings are used without a fabricated fallback label.

When tuning XML and SimData share an ID, tuning takes precedence; SimData is a
fallback and is not counted as a tuning override. Among recognized SimData
definitions, later packages win. This is SDK behavior, not a claim that every
game/mod conflict follows this rule. Unsupported schemas do not yield a
definition, and malformed scanned resources produce `simdata_statistic`
diagnostics. This does not decode other SimData kinds, nested restrictions, or
automatically establish skill XP curves.
