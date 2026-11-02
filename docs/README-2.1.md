# Ember — The Charmander Collection

**2.1.0 — condition-aware buying and PSA 10 upgrades.** This release extends the actual Ember 2.0 Python reconstruction at commit `884d48a2cbe1236f35a79674e317ec02198dd4f8`. It is not recovered code from the legacy Sites application. Python/FastAPI, persistent SQLite and a dependency-free browser interface.

**Delivery status:** implemented and tested locally; **not published to GitHub or deployed to the original website** in this update. The private GitHub account authenticates as `openGallo`, but `openGallo/ember-charmander` was not accessible (404). No Sites deployment controls or authenticated GitHub CLI were available. No original website, unrelated repository, production collection or paid service was changed.

## Run locally

Python 3.12+ (verification used 3.13.5):

```sh
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m ember setup
python -m ember serve
```

Open `http://127.0.0.1:8000`. Choose your owner password during setup: none is included. The server binds to loopback by default and the collection starts empty. Keep the process running. This is local private operation, not an externally hosted deployment.

**Upgrading an existing 2.0 installation:** stop the service after a consistent backup, install the new source/locked dependencies, and keep the same `EMBER_DATA_DIR` and encryption configuration. Do not rerun fresh setup over an existing installation. Startup applies migration 002, retaining IDs, purchase records, original JSON and private photographs. Never run the old 2.0 application on the migrated database; rollback requires the paired pre-upgrade database and configuration. See [upgrade instructions](docs/UPDATE-2.1.md).

## Main workflows

- **Two progress measures:** PSA Gem Mint 10 completion and any-enabled-condition completion. An alternative copy never completes the PSA 10 goal. Multiple copies count once; Ordered copies reserve recorded budget but do not count as Owned.
- **Raw and graded ownership:** preserve original condition wording, raw marketplace scale, grader, grade, special designation and grading era. PSA, BGS and CGC are not interchangeable. “Used” is unknown, not Near Mint. Existing PSA 10 records retain their meaning.
- **Visual binder:** search/filter/sort exact variants, private copy photos, purchase information, separate set/language progress, upgrade flags and condition-specific targets.
- **Buy this card:** comparisons across recorded sources by eligible complete delivered cost, per-category best options, separate incomplete totals, separate auctions, individual listing links, review confidence and provider freshness.
- **Transparent history:** like-for-like completed-sale evidence, recency-weighted reference/range and exclusions. Actual asking-price/bid observations are stored separately. Third-party aggregate guides never become completed transactions or bargain evidence.
- **Personal priorities:** global/per-card fallback categories, PSA-first or value-first ordering, watchlist priorities, seller-location/feedback restrictions and collection budget. Buying a fallback stops more fallback recommendations but keeps PSA 10 upgrade monitoring.
- **Monitoring and in-app alerts:** manual/per-card refresh, a persistent 60-second scheduler wake, saved marketplace interval and pause controls, bounded scan coverage and condition-aware alert deduplication. Purchases, bids, seller messages and offers remain manual.
- **CSV:** validated preview and atomic imports for copies, listings, completed sales and targets; original 2.0 rows remain compatible. Nested settings/targets use JSON cells. Photographs require database backup, not CSV.

## Data sources and activation

| Source | What is implemented | What remains necessary |
|---|---|---|
| eBay | Official OAuth/Browse active listings and item checks; PSA 10 query plus broader query when fallbacks are enabled | Eligible production credentials in Settings, network access, owner review of exact copy and destination costs. Live access not verified here. |
| Cardmarket / TCGplayer via TCGdex | **No-key public aggregate guides** from the documented card API; source currencies/groups/update dates retained | Card page → Refresh free public guides → check base-card ID. API must be reachable. Guide scope may mix languages/conditions/printings and is excluded from bargains. |
| PriceCharting | Optional official read-only Prices API; 24-hour cache, encrypted token, current grade-group estimates | Existing licensed token in Settings and owner-confirmed numeric product ID. No subscription purchased. Prices API is not a completed-sales history feed. |
| Specialist marketplaces / auction archives | Real source-linked manual listings and completed sales, CSV import and direct links | Owner supplies legitimate evidence with exact identity/condition. No automatic broad-site crawling or access-control bypass. |
| TCGdex catalogue / Frankfurter FX | Bounded catalogue discovery and dated reference FX | Accessible public APIs; failures and missing values are explicit. |

Public search links are navigation—not scanned offers. The lowest recorded eligible total is **best found among scanned/recorded sources**, not proof of the lowest price anywhere. Source inventory and connection status appear in Settings. [Detailed coverage and primary documentation](docs/SOURCE-COVERAGE.md).

## Limits and evidence rules

The unchanged catalogue snapshot contains **121 records in seven represented languages: 38 documented and 83 provisional**. It is not a complete worldwide checklist. Unresolved printing identities remain visible but cannot accept ownership or support recommendations. Reference artwork is not evidence of an offered copy; external images may be unavailable.

Raw condition scales and grading designations remain separate. Listing matches require owner review; photo/label/certification checks are owner assertions, not automated authentication. Unknown shipping/fees/import/FX remain unknown. Auction bids are never final purchase prices. Aggregate guide metrics cannot supply a missing sales sample. No precise valuation or “Good buying opportunity” is invented from sparse evidence.

Automatic specialist listing feeds, licensed completed-sale history feeds, automatic photo/certification verification, historic sale-date FX and email/SMS notifications are not connected. No investment-return forecasts or raw-to-PSA-10 promises are made. Manual cost estimates are not tax advice.

## Verification

**243 automated tests passed.** **14 isolated browser/component checks passed**, including 390-pixel layouts. **7 actual local HTTP/process-restart/scheduler checks passed.** Measured statement coverage: **89% for `ember/*`**, 87% including exercised helper scripts. These are not live-provider or deployed-site results.

```sh
python -m pip install -r requirements-dev.lock
python -m pytest
python -m coverage run -m pytest
python -m coverage report --include='ember/*'
node --check ember/static/app.js
python -m compileall -q ember scripts tests
python scripts/audit_tree.py --history
python scripts/http_smoke.py /tmp/ember-http-results.json
python scripts/conditions_ui_checks.py /tmp/ember-ui-results
```

The ordinary browser command uses actual HTTP where permitted. In this environment browser navigation to localhost was blocked by an administrative policy; the documented `--offline-bridge` mode exercised the actual interface with an isolated ASGI backend instead. Real HTTP/process tests were separate. A fresh dependency vulnerability database scan, static type-checker run and Docker build were not performed. See [verification evidence](docs/VERIFICATION.md) and [audit](docs/AUDIT.md).

## Source control and future updates

[Maintenance / private GitHub publication](docs/MAINTENANCE.md) · [Private deployment](docs/DEPLOYMENT.md) · [Monitoring](docs/MONITORING.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](SECURITY.md)

On your computer, with Git and the official GitHub CLI already authenticated as `openGallo`, the included helper can initialize the extracted source and create/publish **only the private intended repository**:

```sh
python scripts/publish_github.py --initialize --publish
```

It refuses public repositories, unrelated destinations, dirty/diverging histories and force-pushes. It does not deploy. Its inclusion is not evidence of a successful upload. The GitHub Actions workflow is manual-only; no runner or hosting charge was triggered. Source archives exclude all runtime configuration, keys, production databases and private photos.
