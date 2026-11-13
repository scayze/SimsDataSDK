# Premade household composites

`PremadeCompositeIndex` indexes type `0x3BD45407` from the installation's
ordered packages. Index once, then request one or more household template IDs:

```python
from sims4_sdk import Installation
from sims4_sdk.premade_artwork import PremadeCompositeIndex

index = PremadeCompositeIndex(Installation(include_mods=True))
result = index.read([12345])
composite = result.largest(12345)  # None if absent or unreadable
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
