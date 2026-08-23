# Gadget Catalog Status

This project is building a normalized catalog of Doraemon secret gadgets for later engineering feasibility analysis.

## Current static sources

- `data/gadgets.seed.json` — curated representative gadgets with Korean names and summaries.
- `data/upstream/yobubble-batch-a.json` — first factual name batch.
- `data/upstream/yobubble-batch-b.json` — second factual name batch.
- `data/upstream/yobubble-batch-c.json` — third factual name batch.
- `data/duplicate-candidates.json` — known aliases, same-Japanese-name collisions, and records requiring manual review.

## Collection rules

1. Preserve factual gadget names and source pointers.
2. Do not republish long third-party descriptions.
3. Prefer Japanese gadget names as the canonical matching key when reliable.
4. Keep English alternative names as aliases.
5. Do not auto-merge suspicious source collisions.
6. Add Korean names and original short summaries during curation.
7. Later classify each gadget by media origin and engineering feasibility.

## Known source-quality issues

The upstream dataset contains some malformed `jp_name` fields such as `General InformationFunctionsDetails`, romanization mixed into Japanese names, and occasional incorrect same-name collisions. These records must be curated before being treated as canonical.

## Target coverage

- Phase 1: representative/curated seed set
- Phase 2: broad public gadget-name collection
- Phase 3: manga-origin cross-check
- Phase 4: anime/movie/game additions
- Phase 5: normalized 1,000+ entry catalog with aliases and provenance
