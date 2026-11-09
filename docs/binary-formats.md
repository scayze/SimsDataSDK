# Binary formats used by `sims4-sdk`

This document records the formats implemented in Step 1 and the values that were
verified against a real installation.  Everything here was checked by parsing
actual game files, not just from documentation.

## DBPF 2.1 container

Files: `.package`, `.world`, `.save`.

```
0x00  char[4]  "DBPF"
0x04  uint32   major version (2)
0x08  uint32   minor version (1)
0x24  uint32   index entry count
0x2C  uint32   index size (bytes)
0x40  uint32   index offset
0x60  ...      resource data
```

The index starts at `index_offset` with a **flags bitmask**:

| bit | meaning |
| --- | --- |
| 0x01 | type is stored once |
| 0x02 | group is stored once |
| 0x04 | instance high is stored once |
| 0x08 | instance low is stored once |

After the flags, the constant fields appear (in the order type, group, instance
high, instance low), then `entry_count` entries.  Each entry contains only the
fields that are not constant:

```
uint32 type / group / instance_high / instance_low   (as needed)
uint32 data offset
uint32 stored size       (high bit 0x80000000 = compressed)
uint32 decompressed size
uint16 compression id
uint16 committed flag
```

* Normal packages use a 32-byte entry.
* Save files commonly set bit 0x02 (constant group), giving 28-byte entries.
* An offset of 0 or a size of 0 marks a null/placeholder entry.

Compression IDs seen in practice:

| ID | meaning |
| --- | --- |
| `0x0000` | uncompressed |
| `0x5A42` | zlib |
| `0xFFFF` | RefPack/QFS |
| `0xFFE0` | null entry in saved games |

## RefPack/QFS

The stream starts with a two-byte magic: `0x10 0xFB` or `0x50 0xFB`.  If the
first byte has bit `0x80` set, a 4-byte big-endian decompressed size follows;
otherwise a 3-byte big-endian size.  The rest is a control-code stream:

| control | meaning |
| --- | --- |
| `0x00-0x7F` | 2-byte code: short back-reference + literals |
| `0x80-0xBF` | 3-byte code: medium back-reference + literals |
| `0xC0-0xDF` | 4-byte code: long back-reference + literals |
| `0xE0-0xFB` | 1-byte code: literal run |
| `0xFC-0xFF` | stop code, 0-3 trailing literals |

Verified sizes: a 2,184,817-byte STBL stream decompresses to 4,307,230 bytes;
a 11,911,027-byte Combined Tuning stream decompresses to 32,487,506 bytes.

## STBL (string table, type `0x220557DA`)

```
char[4]  "STBL"
uint16   version (5)
uint8    compressed (unused)
uint64   entry count
uint16   reserved
uint32   total string size (including one null byte per string)
repeat entry count times:
    uint32 key hash
    uint8  flags (unused)
    uint16 string length (UTF-8, null terminator excluded)
    byte[] string data
```

Header size is 21 bytes.  Verified on `Strings_ENG_US.package`: 58,419 entries,
and sequential parsing lands exactly on the end of the resource.

The locale is the high byte of the STBL instance ID (`0x00` = English).

## DATA tables (SimData `0x545AC67A`, binary Combined Tuning `0x62E94D38`)

```
char[4]  "DATA"
uint32   version (0x100 or 0x101)
int32    table header offset (relative to the field)
int32    table count
int32    schema offset (relative to the field)
int32    schema count
uint32   unused (version >= 0x101)
```

Tables contain a name, optional schema, row size, row count and a relative row
offset.  Schemas contain named columns with a data type, flags and byte offset
inside a row.  Strings are referenced by a relative offset from the field itself
to a null-terminated UTF-8 string.  A relative offset of `0x80000000` means
"null".

Combined Tuning uses exactly seven tables:

0. document metadata (`first_element`, `top_element`, ...)
1. XML nodes (`text`, `attrs`, `children`)
2. attributes (`name`, `value`)
3. node reference array
4. attribute reference array
5. string reference array
6. character data

The decoder reconstructs the original XML tree, so the same `CombinedTuning`
API works for both the XML and binary encodings.

## SimInfo (`.siminfo`, type `0x025ED6F4`)

This is the resource referenced by `PremadeSimTemplate.resource_key`.  It is a
proprietary serialization (version field currently `38`) that interleaves Sim
data with CAS/appearance data.

The part used by Step 2 is the trait list:

```
uint32  version                  (38)
uint32  last_trait_offset        (offset of the last 64-bit trait ID)
...
byte    count
uint64  trait_id                 (count times)
...
CAS/appearance data
```

The list sits immediately before the appearance data.  Walking back from
`last_trait_offset + 8` in 8-byte strides, the count byte is the byte before the
first ID.  Validating the count and every ID against the catalog makes the
recovery reliable (verified on Bella, Mortimer, Alexander, Cassandra, Alex Moyer,
the Burglar, and the Landry household).

Preferences (likes/dislikes) are stored in the same list and are separated by
their catalog class.

## Pre-made Sims

`PremadeSimTemplate` fields:

| Field | Meaning |
| --- | --- |
| `_sim_creation_info.first_name` | 32-bit localization key |
| `_sim_creation_info.last_name` | `specify_last_name` key or `no_last_name` |
| `_sim_creation_info.resource_key` | `.siminfo` resource key |
| `_traits.explicit` | explicit 64-bit trait IDs |
| `_traits.num_random` | number of randomized traits (baked into SimInfo) |
| `_skills.explicit` | skill IDs with ranges |
| `primary_aspiration` | aspiration tuning ID (when pinned) |
| `career_level` | career-level tuning ID (when pinned) |
| `dynasty` | dynasty seed / head / heir / black-sheep flags |
| `occult`, `pregnancy` | occult SimInfo and pregnancy data |

`PremadeHouseholdTemplate` stores `_household_members` (member tag + Sim template)
and `_household_relationship` entries (`is_spouse` or a `family_relationship`
enum such as `FATHER` / `MOTHER` / `MOTHERS_MOM`).

`TunablePremadeAncestor` stores an ancestor's localized full name, gender, death
trait, and thumbnail.

## Verified static extraction (base game + EP13)

| Item | Count |
| --- | --- |
| Traits | 745 |
| Preferences | 166 |
| Aspirations | 191 |
| Careers | 46 |
| Career levels | 223 |
| Developmental milestones | 109 |
| Relationship bits | 268 |
| Merged English strings | 168,469 |
| Pre-made Sims | 36 |
| Pre-made households | 15 |
| Pre-made ancestors | 21 |
| Extraction errors | 0 |

## Verified full static scan (base + all packs + mods)

| Item | Count |
| --- | --- |
| Packages scanned | 616 |
| Tuning entries | 179,499 |
| Traits | 2,795 |
| Preferences | 334 |
| Aspirations | 392 |
| Careers | 146 |
| Career levels | 671 |
| Developmental milestones | 201 |
| Relationship bits | 766 |
| Pre-made Sims | 400 |
| Pre-made households | 191 |
| Pre-made ancestors | 41 |
| Extraction errors | 0 |
| First build time | ~255 s (cached afterwards) |

The full scan includes mods by default. Use `Installation(include_mods=False)` or
`Sims4Workspace(include_mods=False)` for game-only data.

## Verified binary readers

| Check | Result |
| --- | --- |
| `SimulationDeltaBuild0.package` | DBPF 2.1, 135,336 entries |
| `Strings_ENG_US.package` | STBL v5, 58,419 strings |
| Full-build Combined Tuning | XML, `Trait` entries present |
| EP13 delta Combined Tuning | binary `DATA`, 4,749 entries |
| EP13 `DevelopmentalMilestone` | 109 entries |
| Save file (`Slot_*.save`) | constant group index, 61 entries, JPEG + RefPack resources |
| Full game scan | 629 packages, 2,581,974 entries, 0 failures |
| All English string tables | 117 packages, 163,302 strings, 0 failures |
