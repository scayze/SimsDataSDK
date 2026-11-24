# Changelog

Every release lists what changed and, under **Breaking changes**, what you
need to adjust in your project when you update. Breaking changes ship without
deprecated aliases or fallbacks.

## 0.10.0

### Breaking changes

- `starter_household_override(..., sim_traits=...)` is removed. Pass
  `members={sim_id: StarterMemberEdit(trait_ids=[...])}` instead.
- `CollectedPackageData.relationship_modules` is renamed `tuning_modules`,
  and the `include_relationships` argument of `collect_package_data` is
  renamed `include_modules`. The mapping now also holds the lot trait module.
- `PremadeComposite` and `PremadeCompositeResult` are replaced by the shared
  `IndexedArtwork` and `ArtworkIndexResult` from `sims4_sdk.artwork_index`
  (still re-exported by `sims4_sdk.premade_artwork`). Fields are unchanged,
  plus a `shared` flag.
- The static cache version is now `source-resolved-9`; existing caches are
  rebuilt on first use.

### Added

- `StarterMemberEdit` for starter household members: trait list, skills (raw
  XP, merged), current careers, and primary aspiration track.
  `starter_household_override` also takes an inline `description`.
- `starter_household_text` sets the household name and description players
  see, through the lot manifest and new string tables.
- `relationship_loot` builds a loot that sets exact friendship and romance
  values and adds relationship bits, for use with
  `premade_relationship_override`.
- Lot traits and challenges: `LotTrait`, `Catalog.lot_traits`,
  `Catalog.lot_trait`, `Catalog.find_lot_traits`, and
  `Catalog.initial_lot_trait_ids`. `initial_lot_traits_override` changes the
  traits lots start with in a new save.
- `WorldLot.lot_trait_ids` and `WorldLot.house_description_id`;
  `SaveZone.lot_trait_ids` from the save's zone data.
- `LotThumbnailIndex` and `Sims4Workspace.lot_thumbnails()` for the static
  lot previews the game ships, with shared placeholder detection.
- `StringTable.to_bytes`, `SkillCurve.xp_for_level`, and `ACTION_TUNING_TYPE_ID`.
