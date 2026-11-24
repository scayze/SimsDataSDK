# Tray lots and the world lot registry

Use `list_tray_lots(folder)` or `workspace.tray_lots()` for the user's Library.
Each lot groups a `.trayitem`, a `.blueprint`, and the available `.bpi` previews
by their Tray filename instance. The listing surfaces missing or ambiguous item
and blueprint files. Blueprints stay opaque and preview files open on demand.

```python
from sims4_sdk import Sims4Workspace

workspace = Sims4Workspace(include_mods=False)
listing = workspace.tray_lots()
for lot in listing.lots:
    if lot.item is not None:
        print(lot.identifier, lot.item.title, lot.item.creator,
              lot.width, lot.depth, lot.venue_id)
        if lot.preview_files:
            artwork = lot.read_preview()
            png = artwork.to_png()
```

Dimensions and venue IDs come from the blueprint metadata in the `.trayitem`.
The item also exposes the description and the native game timestamp. Pass
`catalog=workspace.catalog` if you want localized venue names. Preview files
are ordered by their resource group, with the lowest group first.

## Select a destination

```python
defaults = workspace.lot_registry()
brook = defaults.lot("Brook Bungalow")
print(brook.region_name, brook.street_name, brook.name,
      brook.width, brook.depth, brook.venue_name, brook.occupancy)

save = workspace.read_save(workspace.latest_save_path())
current = workspace.lot_registry(save)
for lot in current.find_lots(region_id=brook.region_id):
    print(lot.lot_id, lot.zone_id, lot.name, lot.occupancy, lot.household_name)
```

- Group by `region_id` for the named world (e.g. Willow Creek), then by
  `street_id` for its neighborhood (e.g. Courtyard Lane). `world_id` is the
  engine's area ID. `neighborhood_id` is specific to the loaded save.
- The physical lot ID, description ID, template ID, full manifest resource
  key, and save zone ID are distinct identifiers. Use `registry.zone(id)`
  to select a particular save zone when several zones share a physical lot.
  `registry.lot(id_or_name)` returns a result only for a unique match.
- Clean entries use starter manifests, published lot dimensions, and the
  default venue from installed world files. A save contributes names,
  occupants, and recorded venues. `occupancy` is `occupied`, `vacant`, or
  `unknown`. Installed sites absent from a save get `unknown` occupancy.
  The starter household instance remains available as `starter_household_id`
  for reference where known, independently of the current `household_id`.
- Available rows follow the SDK's installed resource scan, which can include
  DLC data shipped in patches. Use `pack` when filtering the clean registry
  to the Studio user's packs. Missing assets, labels, or unsupported layouts
  leave the affected fields unset. Static snapshots can supply geometry and
  strings, and default venue extraction uses the installation's world files.

## Lot traits and static previews

```python
romantic = workspace.catalog.find_lot_traits("romantic")
challenges = workspace.catalog.find_lot_traits(kind="LOT_CHALLENGE")
print(brook.house_description_id, brook.lot_trait_ids)

thumbnails = workspace.lot_thumbnails().read([brook.house_description_id])
preview = thumbnails.largest(brook.house_description_id, unique=True)
if preview is not None:
    png = preview.artwork.to_png()
```

- `Catalog.lot_traits` holds every zone modifier with display info: lot
  traits and lot challenges (`kind`, `is_challenge`), with name,
  description, and icon. The game data has no per-lot trait slot count, so
  the SDK does not expose one.
- `lot_trait_ids` on a clean registry entry are the traits the lot starts with
  in a new save (`Catalog.initial_lot_trait_ids`). With a save overlay they
  are the traits stored on the zone. They are `None` when unknown.
- `house_description_id` is the lot manifest instance. It keys starting lot
  traits and the static thumbnails.
- `workspace.lot_thumbnails()` indexes the 256 and 400 pixel previews shipped
  in `Data/Client/thumbnails*.package`. Only about a quarter of the lots have
  one, from a few worlds. Several lots share one placeholder at 400 pixels;
  `largest(..., unique=True)` skips images whose bytes other lots share.

## Export a new-save move

```python
from sims4_sdk.mods import move_starter_household, write_package

origin = defaults.lot("Garden Essence")
destination = defaults.lot("Brook Bungalow")
resources = move_starter_household(workspace.static_data().world, origin, destination)
write_package("move-bff.package", resources)
```

Use the clean registry and a vacant residential destination. The helper
builds both version 18 manifest overrides for a baked premade household,
including clearing its original assignment. Include both overrides in one
package. The in-game Gallery can place the chosen Tray build.

The lot description and street relationship is described in the
[EA modding forum](https://forums.ea.com/discussions/the-sims-4-mods-and-custom-content-en/updated-more-bt-requests-lot-description-0x01942e2c-and-street-description-0xa68/2591157).
World architecture uses the
[LDNB record bundle](https://llama-logic.github.io/LlamaLogic/packages/LlamaLogic.Packages.Formats.RecordBundle.html).
