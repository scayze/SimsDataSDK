# Scenario and Sim origin integration plan

The SDK should expose game tuning as data first, then derive origin evidence
from explicit links. Scenario use and ordinary-world use are independent;
neither absence nor a dynamic filter proves that a Sim is excluded.

1. Model scenario definitions, roles, NPC filters, template choosers, Sim
   templates, and household templates. Preserve numeric IDs, raw resource
   keys, selected tuning sources, unresolved IDs, and localized text. Reuse
   the existing ordered package scan and reference-aware tuning reader.
2. Link scenario NPC filters to choosers and Sim templates, and link exact
   SimInfo keys to premade Sims. Keep ambiguous matches and dynamic filters
   distinct from proven links; never equate names or partial resource keys.
3. Expose the linked data through static data and the workspace, with stable
   case-insensitive lookups, JSON serialization, portable snapshots and cache
   invalidation. Keep existing origin and ownership filters compatible.
4. Improve normal-world evidence using explicit world placement and spawn or
   household relationships only after verifying their semantics. Separate
   unplaced townies, special NPCs, and test templates instead of classifying
   them from an absence of scenario evidence or the hidden flag.
5. Validate direct, indirect, shared, unresolved, overridden and ambiguous
   references with synthetic fixtures; compare extracted links and origin
   counts with a real installation. Report incomplete coverage explicitly.

The initial implementation covers steps 1–3 for observed fields and NPC
chooser links, and adds residential walkby director → situation → job → filter
evidence for step 4. Director names are a convention; the SDK does not yet
resolve a world to its director. Additional scenario fields, indirect filter
variants, world spawning, and complete classification remain future work; a
partial installation or an older snapshot cannot establish exhaustive coverage.
