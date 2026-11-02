# Monitoring and alerts

## This rebuild versus the original site

This Python application has its own updater and authentication. It does not use the original Sites service bearer and has not changed the old ChatGPT automation. Never reuse old tokens from chat history. No externally hosted monitoring has been verified for the rebuild.

## Runtime

Start `python -m ember serve` on a persistent process. With `EMBER_SCHEDULER=true` (default), the scheduler wakes every 60 seconds. The collection defaults to paused, with a 12-hour marketplace interval. A scheduler wake checks whether a scan is due; it is not itself a marketplace scan. A persistent SQLite lease serializes concurrent updater requests. Scan history is bounded to 100 records and activity to 500 records.

Pause is checked at the start of each execution. A saved pause sends no marketplace requests. Manual owner refresh may bypass the elapsed interval, but not pause. A service caller may bypass neither. Changes made during an already-running HTTP request are applied on the next execution; pause is not an instantaneous cancellation signal.

A marketplace invocation rotates through up to 10 missing, documented variants, with one PSA10 query plus one broader query if enabled, at most 50 search results per query and 10 direct checks of tracked items. Scope, selected languages, watchlist mode, priorities and PSA10 Owned/Ordered exclusions determine eligible cards. An owned or ordered alternative remains a PSA10 upgrade need. Partial batches and truncated search results are exposed. A large scope requires multiple scans. Missing credentials, provider errors and not-due runs remain distinct statuses.

An item disappearing from search is not treated as sold. A direct item response 404/410 marks it unavailable without creating a sale. Changed source identity invalidates prior slab review. Price/destination changes invalidate dependent manual cost estimates as appropriate. New candidates need owner review; the updater does not manufacture a photo/cert verification.

## API and proof

Use the authenticated owner interface or a server-side `Authorization: Bearer` containing THIS rebuild's generated monitor token. Do not place tokens in URLs, browser storage, GitHub files or logs. POST `/api/monitor` once, GET the same endpoint, and compare `last_execution.checkedAt` with the POST's `checkedAt`. The service token cannot read `/api/state` or force an early scan.

`GET /api/monitor` reports scheduler enablement, wake interval, persisted scheduler state and recent run history. A successful POST/GET proves that invocation persisted. A configured schedule is not proof of a timed execution. The saved local verification did observe a `trigger: scheduled` run at the production 60-second interval, with status paused. It proves the loop woke and respected pause, NOT that eBay was scanned.

## Alerts

Only reviewed exact copies in enabled condition/grade buckets with fresh fixed-price observations, complete destination-specific acquisition costs and acceptable budget can meet a target. Bargain alerts also need sufficient completed-sale evidence. A target alert is not a fair-value claim when comparable sales are sparse. Alert identities combine grader-qualified physical certificate (or listing identity), condition/grade bucket, variant, delivered cost, currency and destination. Unchanged offers remain deduplicated across scans and matching certificate duplicates across marketplaces.

Alerts are persisted in-app. They do not reserve money or combine into a jointly affordable shopping basket. Email, SMS, push and webhooks are not implemented. Purchasing and bidding remain manual.

## Public guide refresh is separate

No-key TCGdex guides and optional licensed PriceCharting estimates are refreshed explicitly on a card and cached for 24 hours. They are not scheduled listing scans and never satisfy target/bargain triggers. Provider update dates and observation timestamps are separate from transaction dates. Source errors remain visible without fabricating current guide values.
