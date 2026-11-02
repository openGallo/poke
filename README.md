# Ember — The Charmander Collection

**2.2.0 · Mac desktop edition.** A private Charmander/Salamèche binder, collection tracker and evidence-based buying radar. The code extends the recovered **2.1.0 Git history** (`c7f99376017aef60ff401a0b35b9ac7095b20826`), with the larger catalogue and reference images reconciled from the original Ember Site. The original hosted Site is preserved.

## Open on your Mac

**Prebuilt standalone packages:** both Apple Silicon and Intel packages are built and passed their bundled-runtime startup checks on macOS 15. They include Python and the application dependencies. See [delivery, installation and package checksums](docs/DELIVERY-2.2.md).

1. Check **Apple menu → About This Mac**. Choose `Ember-macos-15` for an Apple chip, or `Ember-macos-15-intel` for an Intel processor, in the [Mac build and downloads](https://github.com/openGallo/poke/actions/runs/41482283641).
2. Extract the downloaded artifact ZIP, then extract the `Ember-macOS-arm64.zip` or `Ember-macOS-x86_64.zip` inside it. Move **Ember.app** to Applications and open it. The directly delivered application ZIPs need only one extraction.
3. Choose your owner password. No terminal or separately installed Python is required for these standalone builds. Scheduled scans run while Ember is open.

The builds are ad-hoc signed and are not Apple-notarized. If macOS blocks the first launch because the developer is unverified, follow [Apple's per-app instructions](https://support.apple.com/en-hk/102445): after trying to open Ember, use **System Settings → Privacy & Security → Open Anyway** for Ember. Other macOS versions and the native window have not been visually verified.

**Delivered source launcher:** unzip `Ember-Mac-launcher.zip`, move **Ember.app** somewhere convenient and open it. First launch needs an installed **Python 3.12 or newer** and internet to install the pinned dependencies. If Python is missing, the launcher offers the official Python download page. Reopen Ember after installation. You do not need to type terminal commands for normal use.

Choose an owner password in the first-run window. Later launches show your private sign-in screen. Personal data lives in `~/Library/Application Support/Ember`, outside the application, so replacing the app does not replace the collection. The collection starts empty; no purchases have been inferred from old conversations or test fixtures.

**From the source folder:** double-click `Launch-Ember.command`. For a self-contained application with its own Python runtime, double-click `Build-Mac-App.command` on your Mac. It builds `dist/Ember.app` and an architecture-specific ZIP. Build on an Intel Mac for Intel, or on Apple Silicon for Apple Silicon. GitHub Actions builds both architectures after application changes are pushed to main; the workflow can also be started manually. Download its architecture-specific ZIP from the repository’s Actions tab.

**Verification limit:** the full 259-test suite, standalone build and bundled-runtime startup checks passed on both macOS 15 runner architectures. Native window rendering, Finder launch, notification delivery and download dialogs have not been visually tested on a Mac. The standalone recipe uses ad-hoc signing and is not Apple-notarized. A minimum version in bundle metadata is not a compatibility test of older macOS releases.


## What you can do

- Define the collection by language, edition, finish, stamp, size and release type. Fresh defaults are **English and French**, accepting **raw NM/Mint or PSA 10**. Other grades are opt-in; an existing installation's saved choices are retained.
- Track Owned and Ordered copies, purchase costs, dates, sellers, certificates and private photos. Count accepted-condition completion and PSA 10 completion separately. Multiple copies do not inflate completion.
- Search the visual binder; save reusable searches; maintain priorities and condition-specific price targets in the watchlist.
- Compare real source-linked listings with complete delivered cost, seller details, listing freshness, photo/condition review and an exact-condition completed-sales ledger.
- See why a deal qualifies, what evidence is missing, which price observations are asking prices, and how sales were included or excluded. A title alone never verifies an offer. Raw NM/Mint is not a promise of PSA 10.
- Group several missing variants from the same recorded seller. Combined-postage savings require a seller quote; the planner does not invent a shipping discount or reserve a basket.
- Estimate the evidence-backed part of the remaining PSA 10 item budget. Unknown cards stay unpriced. A partial estimate is explicitly not a total collection budget.
- Import/export CSV and download a **full private backup** from Settings, including SQLite, photos and matching encryption configuration. Treat that backup as private. See [restore instructions](docs/MAC-DESKTOP.md).

Scans run **while the application is open**, at the saved interval, when monitoring is unpaused and a source is connected. Closing the app or sleeping the Mac pauses scanning. Native notifications are attempted for new persistent alerts; macOS permission and delivery must be checked on the Mac. The Alerts page retains them regardless. No background login item is installed and no purchases or messages are sent.

## Catalogue and identity

The reconciled snapshot contains **485 active variant entries across 11 represented language/region codes**, including **445 documented** identities and **40 provisional** identities. The default English/French scope contains **179 entries**. **195 cached reference images** let most of the binder work without remote artwork requests.

These are dated source records, **not a certified complete worldwide checklist**, a fresh audit of every release, or evidence that every PSA 10 exists. The 10 October 2026 source-check date is preserved. Announcements without confirmed release evidence stay flagged, even if the planned date has passed. Some languages and regional promos remain incomplete. Reference art may show another language, finish or stamp; each applicable note remains visible.

The merger retains all 121 older IDs, maps all 476 original Site entries to distinct active targets, and retires 64 superseded provisional placeholders on fresh installations. Referenced older placeholders and documented user records are retained on upgrades. The Classic set aliases and an ambiguous EB Games foil are reconciled explicitly. Physical variants and base printings are distinguished; a complete census of distinct artwork designs has not been audited.

Catalogue sources and image attribution are retained per card and in `ember/data/reference-assets.json`. [Catalogue merge notes](docs/MAC-DESKTOP.md#catalogue-reconciliation) · [Third-party notices](THIRD_PARTY_NOTICES.md).

## Source capabilities

| Source | Implemented | Requirements / limits |
| --- | --- | --- |
| eBay | Official OAuth/Browse connector for active offers, item checks, scan history and real asking-price observations | Eligible production Client ID/Secret in Settings. No credentials are included. Live authenticated scanning has not been verified. Browse is not a completed-sales history feed. |
| Cardmarket / TCGplayer via TCGdex | No-key, per-card aggregate guide refresh | Public API access and a confirmed base-card mapping. Aggregate prices may combine printings, languages and conditions; they are excluded from exact-condition valuations and bargain labels. |
| Cardmarket listings | Direct research links, manual source-linked observations and CSV | No automatic Cardmarket listing crawler is supplied. Cardmarket's official help page currently says new API applications are closed. |
| PriceCharting | Optional official Prices API connector | An existing licensed token and exact product mapping. No paid account is purchased. The Prices API does not supply individual historical sales. |
| Specialist shops / auction archives | Source-linked listings and disclosed completed sales through forms or CSV | No unsupported continuous scan is claimed. |
| Frankfurter | Dated reference FX | Missing/stale conversion stays unknown; the current rate is not represented as the historical sale-day rate. |

Provider documentation: [eBay Browse](https://developer.ebay.com/api-docs/buy/static/api-browse.html), [Buy API requirements](https://developer.ebay.com/api-docs/buy/static/buy-requirements.html), [Cardmarket access](https://help.cardmarket.com/en/cardmarket-api), [TCGdex market guides](https://tcgdex.dev/markets-prices), [PriceCharting](https://www.pricecharting.com/api-documentation), [Frankfurter](https://frankfurter.dev/v1/).

No demonstration prices, inventory, seller offers or completed transactions enter the shipped runtime. Missing credentials produce a visible blocked scan rather than invented opportunities. A disappeared listing is not a sale. Completed-sale prices, asking observations and aggregate guides stay separate.

## Edit in Visual Studio Code

Open **`Ember.code-workspace`**. It includes interpreter selection, recommended Python/debugger extensions, pytest integration, launch configurations and build tasks.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock -r requirements-desktop.lock
.venv/bin/python -m ember.desktop --debug
```

For browser-based development on Linux, install `requirements-dev.lock` and run `python -m ember.desktop --browser`. Use `--no-open` for a loopback server without a GUI. The versioned package needs Python 3.12+. Normal Mac use remains double-clickable.

| Change | Files |
| --- | --- |
| Interface and styles | `ember/static/app.js`, `ember/static/style.css` |
| Card identity and collection settings | `ember/models.py`, `ember/catalogue.py` |
| Matching and condition buckets | `ember/matching.py`, `ember/conditions.py` |
| Price evidence / ranking | `ember/pricing.py`, `ember/buying.py` |
| Seller grouping and budget estimates | `ember/planner.py` |
| Sources and scan scheduling | `ember/providers.py`, `ember/public_guides.py`, `ember/aggregates.py`, `ember/monitor.py` |
| Desktop launch / setup / notifications | `ember/desktop.py`, `ember/main.py` |
| Mac packaging | `scripts/build_macos.py`, `scripts/mac_bootstrap.sh`, `packaging/Ember.spec` |

To add a marketplace, implement its supported access in a separate provider module, normalize into `ListingIn`, preserve source timestamps and original condition vocabulary, register its capabilities in `ember/sources.py`, and feed the same persistent scan/review/pricing services. Add isolated contract tests; do not advertise a source as connected until a real request succeeds.

To extend the catalogue, use sourced forms or TCGdex discovery in Settings. Provisional records need review before buying advice. `scripts/merge_legacy_catalogue.py` reproduces this reconciliation when the retained original Site checkout is supplied. Never silently replace an established identity.

## Verification and GitHub delivery

Run:

```sh
.venv/bin/python -m pytest
node --check ember/static/app.js
.venv/bin/python -m compileall -q ember scripts tests
.venv/bin/python scripts/audit_tree.py --history
.venv/bin/python scripts/http_smoke.py /tmp/ember-http-results.json
```

The retained browser suite is `scripts/conditions_ui_checks.py`; it requires Playwright's Chromium. Current results and platform limits are recorded in [desktop verification](docs/VERIFICATION-2.2.md). Earlier reports under `docs/verification/` describe earlier releases, not this Mac build.

**Source repository: [openGallo/poke](https://github.com/openGallo/poke).** This is the owner-selected repository; its existing public visibility is preserved. The source repository does not contain your runtime configuration, collection database, personal photographs, credentials, virtual environment or generated app packages.

Clone the repository and open `Ember.code-workspace` in VS Code. To publish later local changes using an authenticated GitHub CLI, use `python scripts/publish_github.py --publish`. The helper permits only `openGallo/poke`, verifies the destination and push permissions, preserves existing visibility, refuses diverging history and never force-pushes. If the selected repository is absent, the helper creates it private by default.

Date-only sales and reference-rate ages use the installation’s local calendar, consistent with entry validation. Operational timestamps remain UTC; local midnight does not invalidate today’s evidence.

The original recovered Git history is preserved separately; see [source provenance](docs/SOURCE-PROVENANCE.md). The original hosted Site remains unchanged. Pushes do not deploy that Site or upload any local collection data.
