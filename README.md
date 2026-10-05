# openscienceworks

## Evidence and data refreshes

The [Reddit backfill record](evidence/reddit-apify-20261005.json) records the
completed Apify run, matching implementation, validated post IDs per DOI,
excluded candidates, counts and source checksum for the 5 October 2026 import.
It is the provenance record for this backfill; active mention lists live in each
story's `signals.social_mentions.reddit`.

Collectors and the dataset importer live in the sibling BookStories repository.
Imports retain existing evidence, update mention totals and render affected
reports. Rebuild `stories_data.js` and the affected publisher portfolios after
an import. A post omitted from a bounded search is not a verified deletion, and
these searches do not establish exhaustive Reddit coverage.
