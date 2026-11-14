# Premade household composites

`PremadeCompositeIndex` indexes type `0x3BD45407` from the installation's
ordered packages. Image instances match the instance IDs of household resources
(`0xB3C438F0`), which can differ from the tuning IDs on `PremadeHousehold`.
Find the household resource in static world data, then look up its instance:

```python
from sims4_sdk import Sims4Workspace
from sims4_sdk.premade_artwork import PremadeCompositeIndex

ws = Sims4Workspace()
record = next((record for record in ws.static_data().world.households.values()
               if record.name.casefold() == 'premadeHouseholdTemplate_BaileyMoon'.casefold()), None)
if record is None:
    raise ValueError('Bailey-Moon household resource not found')
index = PremadeCompositeIndex(ws.installation)
result = index.read([record.instance])
composite = result.largest(record.instance)  # None if absent or unreadable
if composite:
    jpeg = composite.artwork.jpeg
    mask = composite.artwork.alpha_mask
    print(composite.key, composite.package.path)
for issue in result.diagnostics:
    print(issue.stage, issue.package_path, issue.resource_key, issue.message)
```

All readable variants are available in `result.images`. Later packages win
for the same complete resource key; different groups remain separate variants.
`largest` compares decoded dimensions and breaks ties by key. A corrupt winning
resource is reported, not silently replaced by an overridden resource. These
are SDK ordering rules, not a claim about every game or mod load-order case.
Rebuild the index after packages change. Indexing failures and unreadable
resources are reported alongside successful images. The raw JPEG and optional
embedded mask are preserved; the SDK does not infer individual Sim crops.
