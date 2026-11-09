# Sims Wiki validation (Step 4)

The validation layer compares the SDK's extracted data with
**The Sims Wiki** (`sims.fandom.com`). It is optional; install it with:

```bash
pip install -e ".[validation]"
```

## Pipeline

1. **Fetch** — `WikiClient` calls the MediaWiki API (`api.php`) and caches every
   response under `.cache/wiki/requests/`. Pages can be fetched one at a time or
   in batches of 50.
2. **Parse** — `mwparserfromhell` parses templates, links, and tables:
   - `Infobox Sim4`: name, sex, age, career, career level, aspiration
     (`asp`), traits (`trait1..traitN`), spouse, children, parents, family,
     play status, neighborhood.
   - `SkillTable3`: TS4 skill levels.
   - `RelationshipTableSims4` / `RelationshipSims4`: relationship target and
     friendship/romance numbers.
   - Catalog pages: `Trait (The Sims 4)`, `Aspiration (The Sims 4)`,
     `Career tracks`, `Milestone`, `Likes and dislikes`.
3. **Reconcile** — field-by-field comparison with the SDK catalog, pre-made Sims,
   or a save. Statuses are `match`, `mismatch`, `missing_sdk`, `missing_wiki`,
   and `not_available`.
4. **Report** — Markdown and JSON output.

## Commands

```bash
# Compare the first save with up to 50 wiki Sim pages
python examples/validate_wiki.py

# Catalog coverage only
python examples/validate_wiki.py --catalog-only

# Compare static pre-made Sims instead of a save
python examples/validate_wiki.py --no-save

# Bypass the catalog cache / use a specific save
python examples/validate_wiki.py --refresh-catalog --save "Slot_00000002.save"
```

Outputs default to `validation_report.md` and `validation_report.json`.

## Results (local installation)

### Catalog coverage

| Domain | Wiki entries | Matched | Missing | Coverage |
| --- | ---: | ---: | ---: | ---: |
| Traits | 459 | 457 | 2 | 99.6% |
| Likes / dislikes | 125 | 122 | 3 | 97.6% |
| Aspirations | 109 | 108 | 1 | 99.1% |
| Careers | 110 | 110 | 0 | 100% |
| Milestones | 174 | 174 | 0 | 100% |

Remaining missing entries at the time of the run:

- `Death by Heartbreak` — not present in the extracted trait catalog.
- `Positivity Challenge` — likely a newer/event trait not extracted yet.
- `Carnaval Beats`, `Island Radio`, `Suburban Contemporary` — wiki music/decor
  names that do not map cleanly to SDK preference names.
- `Cauldron Connections` — the SDK has the related `Cauldron Concoctions`.

These are exactly the kind of discrepancies the validation layer is meant to
surface; some may be naming differences, others real extraction gaps.

### Save validation

Bella Goth matches the wiki on every available field (**100%**):

| Field | Wiki | SDK |
| --- | --- | --- |
| Age | Young Adult | Young Adult |
| Gender | Female | Female |
| Traits | Good, Family-Oriented, Romantic, Gregarious | same |
| Aspiration | Party Animal | Party Animal |
| Career | Secret Agent / Intelligence Researcher | same |
| Spouse | Mortimer Goth | Mortimer Goth |
| Children | Cassandra, Alexander | same |
| Skills | Charisma, Fitness, Programming | same |

The sample of 20 wiki Sims produced real discrepancies as well, including:

- Nina/Dina Caliente: trait and aspiration differences.
- Don Lothario: career not present in the save.
- Bob Pancakes: wiki lists Iggy Pancakes; the save predates that household
  update.
- Johnny Zest: wiki lists biological parents; the save has no genealogy entries
  for them.
- Nancy/Geoffrey Landgraab: wiki lists Johnny Zest as a child; the save's
  genealogy does not.

These are reported rather than hidden.

### Static pre-made coverage

Comparing `--no-save` is stricter because many base-game pre-made Sims do not
pin age/gender/career/skills in tuning. The validation run also revealed a real
static extraction gap:

- **BFF household** — Liberty Lee, Travis Scott, and Summer Holiday appear in
  saves and on the wiki, but are not emitted by `PremadeSimTemplate` extraction.
  They are likely defined in world-template/starter-save data rather than tuning.
  This should be handled by a world-template extractor in a follow-up.

## False-positive controls

- **Visible traits only** — gender options, walk styles, species, age, and other
  internal traits are excluded from catalog coverage.
- **Spouse semantics** — wiki `{{Spouse|…|Romantic Interest}}` entries are not
  treated as spouses; only spouse/husband/wife/married labels count.
- **Accent normalization** — `Martínez` and `Martinez` match.
- **Slash and fuzzy aliases** — `Master Actor/Master Actress` vs `Master Actor`,
  and minor spelling differences such as `Practicioner` vs `Practitioner`.
- **Skills are a subset check** — the wiki may list only some skills, so SDK
  extras are not counted as errors.
- **Save comparisons only include Sims present in that save** — wiki Sims that
  are simply absent from the save are not reported as extraction failures.
- **`not_available`** — fields such as live relationships are explicitly marked
  unavailable when the save uses legacy relationship chunks.

## Known limitations

1. Wiki pages mix multiple game versions; the parser selects the first
   `Infobox Sim4` whose `game` is exactly `The Sims 4`. Alternate versions and
   gallery makeovers can still cause differences.
2. Some pre-made households live in world-template/starter-save data rather than
   tuning, so static extraction misses them.
3. Live friendship/romance/sentiment values in older saves are stored in legacy
   type-`0x00000006` persistence chunks that are not decoded yet.
4. Wiki tables are parsed heuristically; names can occasionally leak from
   section headings. The parsers filter obvious cases such as `Patch 73`,
   `Music genre`, and compatibility tables.
5. The wiki is community-maintained and can lag behind patches. A mismatch is a
   signal to inspect, not automatically an SDK bug.

## Refreshing the cache

```bash
rm -rf .cache/wiki          # PowerShell: Remove-Item -Recurse -Force .cache/wiki
python examples/validate_wiki.py
```
