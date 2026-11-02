# Ember 2.2 verification — 2 November 2026

## Passed in this environment

- **255 automated tests**, including the original condition/pricing suite and new first-run setup, private backup, stable catalogue migration, source-alias coverage, saved searches, strict fresh defaults and seller-basket tests. Current run: 41.68 seconds. See `verification/v2.2/pytest.xml`.
- **7 real local HTTP/process checks**: server startup/authentication; purchase persistence across a full process restart; cleanup of synthetic ownership; scheduled/manual scan heartbeat; the actual 60-second scheduler wake; missing-source status with no fabricated offers; consistent SQLite backup. See `http-results.json`.
- **4 additional real desktop-process checks** passed: ephemeral loopback startup; first-run password setup and login over HTTP; raw NM ownership without PSA 10 completion; full process restart preserving the password, configuration and copy. See `desktop-process.json`. These exercise Linux server lifecycle, not the native Mac window.
- **A real TCGdex request** through the app returned 15 public aggregate guide observations (HTTP 200, connected). The isolated database still had zero completed sales and zero listings. These observations were not added to the delivered collection. See `live-public-guide.json`.
- JavaScript syntax, Python compilation, shell syntax and the outgoing source/history check passed. Reviewed reference-image hashes are explicitly allowed by the source check; personal runtime files remain excluded.
- The combined development and desktop dependency locks resolved together in a dry run. No macOS-specific package was executed on Linux.
- Source-launcher ZIP created with a valid application-bundle layout, Info.plist, executable shell launcher, source resources, reference images, icon and first-use instructions. Native execution remains unverified.

## Interface review

The managed preview environment did not contain this project's Python dependencies, so a live browser-to-Python preview was unavailable. Its supported static preview was used to display **recorded real GET responses from an isolated, empty app instance** with the actual interface code and cached artwork.

The dashboard, binder, saved-search form, purchase planner, settings and first-run form were inspected in the cloud browser. This review found and corrected the saved-search control placement/availability and missing foil/edition labels. The settings view showed only NM/Mint raw buckets selected by default, with English and French as the initial scope. Screenshots showed readable layouts and genuine reference artwork. The first-run password fields were viewed, not submitted through the static preview. Browser-extension metadata errors were unrelated to application code.

This is **layout and navigation review**, not an authenticated browser-to-backend test. Real mutation/persistence/authentication behavior is covered separately by API and HTTP tests. The retained Playwright end-to-end suite was attempted but could not run because its Chromium executable is not installed. No passing end-to-end browser or new mobile-layout result is claimed.

## Original project and collection

Recovered the original local React/TypeScript Site source and the 2.1 Python source ZIP/Git bundle. The latter's complete Git history is retained as the desktop base. Original Site access and deployed content were not changed.

The deployed database was read through its supported read-only tools. The complete `collection_copies` result was empty. The complete `records` result contained one blocked eBay scan and no collection, watchlist, listing or sale records. No current collection copies were available to migrate. No provider credentials were read or copied.

## Not verified or not connected

- Cocoa/WebKit, Finder launch, Mac download dialogs, native notifications and the final standalone executable require a real Mac. The host is Linux; PyInstaller does not cross-build a tested macOS executable here.
- No Developer ID signing or Apple notarization. The Mac build script's ad-hoc signing is clearly identified.
- No authenticated live eBay or PriceCharting scan, licensed completed-sales feed, continuous Cardmarket listing crawler, automatic shop crawling, automatic photo/certification authentication, or predicted raw-to-PSA-10 outcome.
- Worldwide catalogue completeness and a complete artwork-design census remain unverified. The 485 active entries are a partial, dated checklist with 40 provisional identities; the fresh English/French scope has 179 entries.
- Background operation after quitting is not installed. Scanning runs while Ember is open, at the saved interval, when unpaused and connected.
- No GitHub upload: the authenticated connector identifies openGallo, but the intended repository returns 404 and the connector cannot create repositories. The available browser reaches GitHub's sign-in screen. The local history and publication helper are ready; no unrelated repository was used as a substitute.

Older evidence under `docs/verification/` is retained as historical provenance. It does not verify this release's Mac package.
