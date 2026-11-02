# Verification — Ember 2.1.0

**Scope:** the local maintained Python reconstruction. Date: 10 October 2026. Base revision `884d48a2cbe1236f35a79674e317ec02198dd4f8`. No live user database or credentials were used. The legacy website and GitHub destination were not changed.

## Executed results

| Check | Observed result | Evidence |
|---|---|---|
| Baseline 2.0 suite before edits | 151 tests passed | Base archive inspected and baseline rerun |
| Updated automated suite | **243 passed; 0 failed, 0 errors** | `v2.1/pytest.xml`, `v2.1/tests.txt` |
| Statement coverage of application modules (`ember/*`) | **89%**; 2255 statements, 244 missed | `v2.1/coverage-app.txt` |
| All exercised modules plus helper scripts | 87%; 2419 statements, 309 missed | `v2.1/coverage-all.txt` |
| Browser/interface checks | **14 passed**, no uncaught JS errors; 390px layouts | `v2.1/ui-results.json`, labelled screenshots |
| Actual local HTTP/process checks | **7 passed**, including full OS process restart | `v2.1/http-results.json` |
| JS parse and Python compilation | Passed | `v2.1/static-checks.json` |
| Known-pattern outgoing source and history scan | Passed at packaging | `v2.1/source-hygiene.json`; rechecked after local commit |

Two previous tests asserting unconditional rejection of other graders/PSA9 were revised for the newly authorized scope. The legacy contradictory-match expectations remain tested; new tests cover selected-category matching. Passing count is an observed total, not a count of unique user requirements.

## Commands

```sh
python -m coverage run -m pytest -q --junitxml=/tmp/ember-v21-pytest.xml
python -m coverage report --include='ember/*'
python -m coverage report --omit='tests/*'
node --check ember/static/app.js
python -m compileall -q ember scripts tests
python scripts/audit_tree.py --history
python scripts/http_smoke.py /tmp/ember-http-results.json
python scripts/conditions_ui_checks.py /tmp/ember-ui-results --offline-bridge
```

Python 3.13.5, Node 22.16.0, system Chromium and Playwright 1.57.0 were used. Dependencies remain locked. No JavaScript bundling pipeline is required.

## Browser method and exact limit

Direct Playwright navigation to local HTTP was rejected with `ERR_BLOCKED_BY_ADMINISTRATOR`. That policy was not bypassed. The `--offline-bridge` mode mounts the actual browser assets and calls the actual isolated FastAPI application through a local ASGI testing bridge; external image/network requests are blocked. Browser steps test owner login, two completion metrics, guide-mapping review, raw ownership, category targets, listings/cost review, a disclosed raw test sale, separate PSA history, pause UI, settings and deal filters, plus 390px binder/card/settings layouts.

This is **component/interface integration**, not successful real browser-network or deployed-site testing. A future allowed environment can run the same command without `--offline-bridge` for actual browser HTTP. A separately executed process script uses real HTTP to Uvicorn and a full OS-process stop/restart. Both methods are documented rather than being conflated.

All screenshot values are synthetic test inputs or the authentic empty catalogue view, never live purchase opportunities. Missing images in screenshots are intentional remote-image blocking, not invented artwork. User-provided private photos and secrets are absent.

## Updater evidence

The actual local HTTP script invoked POST `/api/monitor` once and verified the GET readback under the rebuild's supported authorization:

- Manual `checkedAt`: **2026-10-10T11:56:10.843197+00:00**; status `paused`.
- Observed scheduled `checkedAt`: **2026-10-10T11:57:10.751627+00:00**; trigger `scheduled`; status `paused`.
- The saved result records zero marketplace requests/results. The schedule actually woke at the 60-second interval and respected pause. This is not a successful marketplace scan or a run on the original hosted website.
- A separate unpaused check with no eBay credentials correctly returned `missing_credentials` without fabricated data. A SQLite backup completed and passed integrity verification.

## Source and remote checks

Authenticated GitHub profile: `openGallo`. The intended repo returned 404 / not accessible. Repository-creation actions and authenticated `gh` were unavailable, so no upload was attempted against an unrelated destination. No Sites deployment controls were available. The host working for the owner does not grant this session source/deployment access.

TCGdex's documented no-key guide endpoint was requested through ordinary server networking and failed DNS resolution. No live guide values were stored. PriceCharting/eBay tests used official API response-shape fixtures, not authorized live calls. Cardmarket's direct export pages were not accessible through web retrieval; its public export availability was confirmed in its own published documentation. The implemented no-key guide adapter uses TCGdex, not a speculative scrape of protected pages.

## Not performed / not claimed

No externally deployed URL health/persistence test, GitHub CI execution, Docker image build, formal static type checker, fresh dependency advisory database scan, penetration test, automatic certification verification, global catalogue census or licensed completed-sale feed test. Neither locked packages nor a known-pattern secret scan constitutes a security guarantee. Source publication, deployment, configured scheduling and observed scans remain separate outcomes.

Existing files directly under `docs/verification` are retained **historical 2.0 evidence**. The `v2.1` subdirectory is the evidence for this release. JUnit parameter text containing a deliberately invalid fixture URL credential is redacted in the distributable report; no test result/count is changed.
