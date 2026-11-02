# Engineering audit — condition-aware update 2.1

**Date:** 10 October 2026. **Audited source:** the actual 2.0 reconstruction plus the 2.1 patch in this repository. This is not an audit of inaccessible legacy Sites code or a certification of perfect security. Evidence: VERIFICATION.md and the committed `docs/verification/v2.1` results. No production records were used for testing.

## Requirements-to-implementation mapping

| Requirement | Implemented files / exercised behavior | Remaining limits |
|---|---|---|
| Exact catalogue identity and languages | `catalogue.py`, `models.py`: unchanged immutable physical variant IDs, provisional gates, source/coverage; existing tests rerun | Partial 121-record seed, 83 unresolved; no new census or guaranteed remote art |
| Raw/graded state independent of identity | `conditions.py`, `models.py`, `matching.py`; exact raw scale, grader, grade, designation/era; conflicting source evidence rejected | Conservative vocabulary and human condition assertions; no image grading |
| Dual completion and upgrades | `main.py`, `conditions.py`; distinct variants; alternative/Ordered handling; PSA10 upgrades still needed | Single owner; disabled fallbacks intentionally not counted as acceptable ownership |
| Preserve purchases/photos and CSV | migration002 + compatibility reads; certificate namespacing; transactional CSV preview/roundtrip; legacy format migration fixture | Actual legacy Sites/D1 export not migrated; CSV not a photo backup |
| Cross-source offers and real links | `providers.py`, `buying.py`, `sources.py`; eBay official adapter, manual source evidence, search links labelled; direct cheapest complete cost per category | No live production eBay test; manual specialist offers not auto-refreshed |
| Comparable historical evidence | `pricing.py`; exact category and physical ID; sparse data, undisclosed offers, duplicates, outliers and recency handled | Mainly manual completed-sale evidence; current FX not historic sale-date FX |
| Costs/auctions/seller/budget | complete versus lower-bound totals; delivery/country/feedback filters; auctions separate; Bought/Ordered commitments | Fees/imports require real evidence; no automatic tax engine or combined portfolio optimizer |
| Historical asking prices and guides | `observations.py`, `aggregates.py`, `public_guides.py`; actual observed changes only; guides isolated, dates/scales/currencies explicit | Public guides can mix conditions/languages/printings; never bargain inputs; network not verified |
| Targets, priorities and alerts | `conditions.py`, `monitor.py`; category-specific targets, fallback overrides, priority, dedupe, budget, existing ownership | One known acceptable fallback is sufficient; no resale/profit/grade-probability predictions |
| Scheduling and coverage | SQLite lease, pause/interval rules, bounded PSA10+broad query coverage, known errors; actual local scheduled pause observed | Always-running process needed; hosted schedule untouched; provider access unavailable |
| Security and safe integrations | owner login/session, CSRF/host/origin, encrypted credentials, allowlisted fixed-host reads, safe uploads; known-secret hygiene scan | No MFA/SSO, external penetration test, fresh dependency advisory scan or formal static types |
| Interface and accessibility basics | real copy/listing/review/sale/target/settings forms, comparison, category charts, source/error states; accessible select labels; 390px layouts | Offline component integration due browser-network policy; no exhaustive accessibility certification |
| Delivery and deployment | maintained source history, locks, migration, CI template, private publish helper, source archive | GitHub destination404; no GitHub upload, original site update or external service provisioning verified |

## Confirmed defects corrected during implementation

The first four rows are necessary changes to previously PSA10-only behavior rather than claims that 2.0 violated its former specification. Later rows are defects found while reviewing the extension.

| Priority | Confirmed failure/risk in reviewed code | Correction and regression evidence |
|---|---|---|
| High | Old completion counted any copy and old model rejected alternative grades | Distinct PSA10 and accepted-any sets, actual alternative flags; API/migration tests and raw-form browser check |
| High | Previously a variant alone selected completed-sale comparables | Category key includes raw scale or grader/grade/designation/era; adversarial mixture tests require like-for-like observations |
| High | Previously variant ownership could stop all scans | Alternate ownership leaves PSA10 need; targets keyed by condition; source-contract test checks separate PSA10 and broad searches |
| High | Old certificate uniqueness was global, not grader-qualified | Non-destructive PSA namespace migration and company-qualified index; migration preserves original JSON/photo fields |
| High | Generalizing to alphanumeric graded certs weakened the explicit PSA review restriction | PSA review remains 6–12 numeric digits; BGS/CGC namespace independent; API regression |
| Medium | First eBay shipping option could be dearer than another valid option | Select minimum finite nonnegative option in matching currency, leave taxes/fees unknown; source test |
| Medium | A non-object price-guide response could raise an uncontrolled exception | Validate provider shape and requested product; sanitized explicit error; no partial values saved |
| Medium | Changing watch target currency could silently re-denominate retained targets | Form prevents currency change with another retained target, including legacy PSA10 target; no implicit conversion |
| Medium | A provider disconnect initially purged all guide rows | PriceCharting disconnect deletes only its own aggregates/cache; public-guide test verifies independent observations survive |
| Medium | Inferred raw condition/original vocabulary could conflict | Preserve original description and source scale; reject positive contradictions; unknown stays non-recommendable |
| Low | Select accessible names included nested option text | Explicit aria-labels; exact browser locators work for history, condition and deal selectors |
| Low | Notes UI accepted more characters than server validation | Align textarea maximum to model limit; show server errors rather than silent data loss |
| Low | Browser-check script treated `--help` as an execution request | Real argparse flags; help exits without starting a server or browser |

## Tested preventive boundaries

No completed sale is fabricated from an ask, aggregate, hidden offer or disappeared listing. No confirmed contradiction can be waived by a checkbox. No complete price is claimed when fees, imports, shipping or conversion are unknown. No raw or non-PSA grade completes the PSA10 metric. Owner-entered evidence remains an assertion, not automatically authenticated truth. Public API requests are fixed-host and size/rate/caching bounded. Credentials are encrypted at rest and never part of client state, source archives or reports.

Price-chart time series contain real observed points only. Provider daily/weekly/monthly averages are displayed as aggregate groups, not converted to invented historical sales. Weighted IQR ranges are dispersion summaries, not confidence intervals. Seller ratings/photographs are not guarantees of authenticity or fulfillment. Budget gating applies per opportunity and does not reserve funds for all simultaneous alerts.

## Explicit verification gaps

No live marketplace or guide prices were obtained in this environment. Original hosting controls were absent, and the intended GitHub repository was inaccessible. Container image building and deployment, direct specialist APIs, historical-sale licensed feeds, automatic slab/cert checks, external notifications, formal dependency advisory scanning, formal static type-checking and comprehensive accessibility/penetration testing remain unverified or unimplemented. These are not described as passing tests.
