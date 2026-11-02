# Architecture

## Provenance

Version 2.1.0 extends the actual delivered 2.0.0 reconstruction, whose base source was newly implemented from the requirements. No original Sites code, D1 database, credentials, or ownership records were recovered or migrated. The owner identified the original URL as https://ember-charmander.abuzz-gull-8763.chatgpt.site/; it is preserved, not replaced. Current local network lookup failure is not evidence that the owner's app is offline.

## Components

`ember/main.py` is the FastAPI HTTP boundary and owner-only API. `models.py` validates input and immutable variant IDs. `db.py` handles SQLite WAL, transactions, migrations and leases. `catalogue.py` seeds and incrementally discovers source-linked records. `matching.py` rejects explicit identity/grade contradictions and produces candidates. `pricing.py` calculates complete versus lower-bound costs, transparent robust references, budgets and assessments. `providers.py` contains fixed-host official API adapters. `monitor.py` owns scheduled scans and alert fingerprints. `conditions.py` models category identities and upgrade needs; `buying.py` assembles like-for-like comparisons; `observations.py` stores changed asks/bids; `public_guides.py` retrieves no-key contextual metrics and `aggregates.py` handles optional licensed price guides. Neither guide adapter writes completed sales. `sources.py` is the explicit capability inventory. `security.py` handles login sessions and encrypted provider credentials. `config.py` loads secret configuration without returning it to clients.

The browser uses native ES modules and CSS from `ember/static`. No client framework, Node dependency tree or bundling build is required. Every mutating control calls the server with CSRF protection; user/remote strings are HTML-escaped. Search, filter, pagination and route state are client-side while collection records persist in SQLite. All source and assets needed to serve the interface are in the archive; external card artwork remains a source dependency.

## Database

Tables: `schema_migrations`, `kv`, `variants`, `copies`, `watchlist`, `listings`, `listing_matches`, `sales`, `alerts`, `activity`, `sessions`, `rate_limits`, `locks`, `scan_log`, `images`, `listing_history`, `aggregates`. Foreign keys bind records to exact variants. Nonempty certification numbers are unique within a grading-company namespace across owned/ordered copies. Migration 002 qualifies legacy PSA numbers without rewriting original record JSON, copies, images or IDs. Listings use canonical source URLs. Sale transaction keys and alert fingerprints have unique constraints. Photos are re-encoded private BLOBs.

One owner, one persistent process, one SQLite database is the supported production topology. The process scheduler shares a database lease with manual/service refresh, preventing concurrent scans. Do not run on ephemeral storage or sleep-to-zero hosting and expect continuous monitoring or persistence.

## Data flow

Catalogue source → provisional exact-identity research → documented variant → owned/ordered record or listing candidate → explicit photo/label/cert/identity review → comparable completed-sale calculation → target/bargain alert. Source access, catalogue existence, slab match and price confidence remain separate.

Versioned source belongs in GitHub. Runtime configuration, credentials, collection state, photos, sessions and database backups do not. The old application's data requires a separately reviewed export-to-identity mapping before import; identifiers are not assumed compatible.

Conditions are properties of copies/listings/sales, never part of physical variant IDs. Comparable categories are raw-source-scale plus condition, or grader plus grade plus designation plus era. Separate completion sets and upgrade needs are derived rather than stored inconsistently. Guide metrics and asking observations are separate tables, so unsupported evidence cannot silently enter the sales estimator.
