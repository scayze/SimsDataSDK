# Mod tuning candidates

`catalog.tuning_overrides` maps tuning IDs to ordered lists of candidates for
IDs seen more than once where at least one candidate came from a mod package.
Each candidate records its tuning name, class, package path, pack, mod flag,
and containing resource key. The last candidate is the definition selected by
the SDK. An empty mapping means no qualifying collisions were seen; `None`
means history was unavailable, such as in an older portable snapshot.

```python
history = workspace.catalog.tuning_overrides
if history is not None:
    for candidate in history.get(16699, []):
        print(candidate.name, candidate.source.path, candidate.source.resource_key)
```

The lists capture *occurrences*, not a diff: retail combined-tuning blobs can
be duplicated byte-for-byte, and a collision does not prove the candidates
have different semantics. Full overridden tuning bodies are not retained. Pure
retail collisions are omitted to limit memory and output size. Package order
is the SDK's deterministic order, not a guarantee of the game's resolution of
every mod conflict. The history covers successfully decoded combined tuning,
generic tuning XML, and known class-hashed XML types in mod packages; unparsed
formats and SimData companions are excluded. Extraction diagnostics identify
read or decode failures where known, so absence of a candidate is not proof it
does not exist in an unsupported resource.
