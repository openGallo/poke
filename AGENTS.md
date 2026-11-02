# Maintaining Ember

This is the Python/SQLite 2.x reconstruction, not the legacy ChatGPT Sites app.
Read README.md and docs/UPDATE-2.1.md before changing semantics.

- PSA Gem Mint 10 remains the ultimate completion goal. Raw and other grades are explicit alternatives; never count them toward PSA 10 completion.
- Variant identity is independent of copy condition. Keep existing IDs and user records stable.
- Raw condition scales, graders, grades, special designations and CGC eras are distinct comparison buckets.
- Only reviewed copies and exact-condition disclosed sales may support recommendations. Unknown costs remain unknown. Auctions are not final prices.
- Real marketplace data only. Synthetic fixtures must remain isolated from runtime/seed data.
- Preserve private authentication, CSRF, encrypted credentials and safe migrations. Never commit runtime files, tokens or production photos.
- Run pytest, JS syntax/compilation, current UI tests and source/history hygiene checks. Distinguish offline UI tests, real HTTP checks, live provider scans and deployments.
- Destination: openGallo/poke, explicitly selected by the owner. Preserve its existing visibility (currently public). Keep all collection data and credentials outside Git. Never touch unrelated repositories or force-push.
