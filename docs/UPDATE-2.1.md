# Update 2.1 — alternatives without losing the PSA 10 goal

## Provenance and upgrade

This is an extension of the delivered 2.0 reconstruction, not a new replacement scaffold and not an update to the old Cloudflare/Sites deployment. Base revision: `884d48a2cbe1236f35a79674e317ec02198dd4f8`. Application version: 2.1.0. Dependencies and catalogue identities are unchanged.

1. While the old service is running, make a consistent backup with `python -m ember backup /secure/path/ember-before-2.1.sqlite3` and keep its matching private configuration/key separately. Verify your backup.
2. Stop the old process. Replace only source/dependency files. Keep the same `EMBER_DATA_DIR`, database and configuration; do not unpack over private runtime data or initialize new keys.
3. Install `requirements.lock`, then `python -m ember serve`. Startup runs migration 002 inside the existing migration mechanism. Check login and your real counts without creating test purchases in production.
4. Raw/graded fields are read compatibly for old records: an absent grader/grade means legacy PSA 10, not a raw card. The SQL certificate index becomes grader-qualified; original stored JSON is not rewritten. Existing IDs/photos/transactions are retained.
5. A rollback must stop the new process and restore the paired pre-upgrade database/configuration along with the 2.0 source. Old code is not compatible with the grader-qualified certificate index or new alternate records.

Migration tests create a synthetic actual 2.0-format database and confirm IDs, original JSON and photographs remain unchanged after upgrading. No actual user's legacy Sites/D1 data was available or migrated; that format needs a separately reviewed export and identity map.

## Configure fallback collecting

Settings → PSA 10 & fallback buying preferences. Default accepted fallbacks are PSA 9, seller/TCGplayer/Cardmarket Near Mint and eBay Near Mint or Better. BGS/CGC and lower raw categories are opt-in. Multiple selection is explicit; per-card watch settings can override the global list or disable alternatives.

The first metric always counts actual Owned PSA 10 variants. The second counts Owned copies in an enabled condition. Ordered copies reserve the recorded budget, never completion. The binder labels alternate-only ownership as a remaining PSA 10 upgrade. A stored copy in a disabled fallback category is retained physically, but does not silently count as accepted-scope completion.

On a card, Record a copy → choose a category → preserve original wording → confirm the actual printing/condition → enter purchase fields. Raw copies have no slab cert or grade. Graded Owned copies require a certificate; the namespace is grader-qualified, so unrelated companies can use the same number. Owner photos are private, re-encoded and persist in SQLite.

## Conditions and matching

A raw price bucket contains condition **and its source scale**. Cardmarket EX/Good/Played/Poor are not mapped to another marketplace's NM/LP/MP/HP. “Used,” “New,” ambiguous ranges and unknown descriptions remain Unknown. An explicit owner-normalized category may be recorded after inspecting the copy; contradictory original descriptions are rejected during listing review.

Graded buckets contain company, numeric grade, designation and grading era. PSA 10 is Gem Mint; BGS Black Label and Pristine are distinct. CGC current/legacy eras remain separate, and an unspecified CGC era cannot generate a recommendation. Owner review is not automated image assessment or a certificate-authenticity guarantee.

Old simple `target_price` is PSA-10-only. New `targets` contains condition-keyed amounts; changing the target currency requires clearing incompatible retained targets first. Existing target amounts are never silently re-denominated.

## Compare and evaluate

Buy this card displays reviewed fixed offers with confirmed total/delivery separately from incomplete totals and auctions. It keeps unreviewed candidates visible for inspection. Source status distinguishes an unavailable scan from a no-result scan and budget-exceeding known offers. “Best” is scoped to recorded or checked offers, not the entire internet.

For each exact category, qualifying completed sales feed the existing robust method: default 180-day lookback, 60-day recency half-life, normally at least five qualifying observations, sample-adequacy checks and documented log-MAD outlier handling. The reference range is a weighted interquartile spread, **not a statistical confidence interval**. Every included/excluded observation is inspectable.

The cost comparison uses current estimated delivered cost against historical item-only prices and labels this conservative difference. FX is dated current reference conversion, not historical day-of-sale FX; that limitation is stated. Unknown acquisition components are lower bounds and do not earn bargain/target eligibility. An undisclosed accepted offer, source aggregate or current ask is never a realized sale.

Asking-price/bid/cost/status observations are captured only when actually observed and changed. The history plots real points; it does not invent daily observations or create sales from disappeared listings. Existing listings have no fabricated pre-upgrade history.

## Sources

- eBay credentials enable supported Browse queries. A missing documented variant can get one PSA10 query and one broader query when fallbacks are enabled; matching remains exact. Candidate photos/labels/certs and full destination costs must be reviewed before advice.
- Free public guides use the documented TCGdex card API. Confirm the base-card ID (for example a suggested set/local-number ID); the returned ID, name, number and set must agree. Values retain provider/currency/groups/update dates. Guide scope may mix conditions, language and physical variants. It remains context only, excluded from all market-reference and bargain calculations.
- PriceCharting uses an existing licensed Prices API token, stored encrypted. Confirm its numeric product mapping. Only current aggregate fields are stored, never its token or a fabricated history. Disconnect purges only this provider's cached values, not public guides, collection records or sales. No subscription is activated.
- Specialist exact listings/sales can be entered with direct HTTPS evidence or CSV. External research links do not claim scan coverage or a cheapest offer. No anti-bot, paywall or authentication bypass is attempted.

All new provider contracts were tested with isolated synthetic fixtures; this environment could not resolve the TCGdex API for the live no-key request, and no live eBay or PriceCharting credentials were available. Integration implementation and successful external connection are different outcomes.

## Monitoring / alerts

The scheduler checks saved pause and interval. Fallback ownership or an ordered fallback suppresses further fallback buying needs but keeps PSA10 upgrade searches. Existing PSA10 Owned/Ordered records suppress duplicate purchases. Seller restrictions, priorities, targets and budget apply before alerts. A target alert can have insufficient historical valuation evidence, but says so; it is not a bargain claim.

Fingerprints include condition, grader-qualified certificate/listing, exact variant, delivered total, destination and currency. Unchanged cross-posts of the same reviewed slab do not repeatedly alert. Raw listings without a shared cert are not aggressively merged. No purchase, bid, offer or message is sent.

## Acceptance evidence

See VERIFICATION.md for the executed commands and artifacts, and AUDIT.md for confirmed defects and limitations. The legacy website and original hosted schedule were unchanged. The local source checkpoint/bundle is not proof of GitHub publication or a live deployment.
