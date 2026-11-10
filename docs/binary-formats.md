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

## Lot/household manifest (type `0x729F6C4F`)

One record per lot, stored in each pack's `Simulation*` and `Client*` packages.
The record lists the lot name/description and, when a pre-made household lives
there, the household name/description plus the household resource reference.

94-byte record (base game / client builds):

```
0x00  uint32  count/flags (usually 7)
0x04  uint32  lot name STBL key
0x08  uint32  lot description STBL key
...
0x46  uint32  lot record id (varies per lot)
0x4A  uint32  0
0x4E  uint32  household name STBL key
0x52  uint32  household description STBL key
0x56  uint64  household resource instance (0xB3C438F0)
```

The Preload/Delta builds use a 162-byte record with the same block at `0x72`;
the SDK locates it by searching for a `(name_key, description_key, uint64 id)`
triple and validating the ID against the household resources that exist.

## Pre-made household (type `0xB3C438F0`)

Protobuf document with a small binary header.  Two header layouts occur:

```
version 0:  uint32 version=0, uint32 payload_length      (8 bytes)
version 2:  uint32 version=2, uint32 0, uint32 0, uint32 length  (16 bytes)
```

Payload message:

```
field 1  message   household
  3  string   household name            ("BFF")
  4  varint   household funds           (9000)
  6  message  repeated member
       1   fixed64  Sim ID
       5   string   first name
       6   string   last name
       7   varint   gender flag   (0x1000 male, 0x2000 female)
       8   varint   age flag      (4 child, 8 teen, 16 YA, 32 adult, 64 elder)
      12   string   body/genetics float list
      30   message  gameplay
            10  message  { 1: packed trait IDs }
            12  message  { 1: repeated { 1: career, 2: track, 3: track level, 4: display level } }
            13  message  { 1: repeated { 1: skill statistic, 2: float value } }
      34   varint   aspiration track ID
```

The age also appears as a trait (`trait_youngAdult`, `trait_adult`, ...), which
the SDK prefers.  The career entry's field 3 is the 0-based track level (it
matches the save's `SavedCareer.track_level`) and field 4 is the 1-based display
level; indexing `CareerTrack.level_ids` with field 3 gives the exact starting
job title (Quality Assurance, Module Cleaner, Intelligence Researcher, ...).
Verified on the BFF, Goth, Pancakes, Roomies, Spencer-Kim-Lewis and Caliente
households against the same Sims in a real save.

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

## Verified full static scan (base + all packs, no mods)

| Item | Count |
| --- | --- |
| Packages scanned | 602 |
| Tuning entries | 179,499 |
| Traits | 2,795 |
| Preferences | 334 |
| Aspirations | 392 |
| Careers | 146 |
| Career levels | 671 |
| Developmental milestones | 201 |
| Relationship bits | 766 |
| Pre-made Sims | 431 |
| Pre-made households | 204 |
| Pre-made ancestors | 41 |
| Lot manifest records | 548 |
| Extraction errors | 0 |
| First build time | ~275 s (cached afterwards) |

`Installation(include_mods=True)` adds 16 mod packages on this machine (618
total). Use `Installation(include_mods=False)` or
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
