# Catalogue and source coverage

Snapshot: 10 October 2026. The rebuild contains 121 source-linked records, 38 source-documented printing identities and 83 provisional records, across seven represented languages: English, Japanese, French, German, Italian, Spanish and Portuguese. Twelve languages are selectable; selected-but-unrepresented languages do not imply coverage. This is a partial research seed, not a comprehensive global census.

`ember/data/catalogue.json` is the delivered snapshot. `scripts/make_seed.py` reproducibly rebuilds it. Each record keeps a source URL and check date. The ID hashes normalized language, set code, card number, edition, finish, stamp, size and print run. Zero-padding is not a new collectible. Names, explanatory notes and year corrections do not change the identity. Distinct editions, stamps, sizes and foils do.

## Evidence

TCGdex source files document localized names and variants. Bulbapedia's Charmander checklist and individual release pages establish other physical printings. Only specifically represented ordinary localized treatments were added across languages; regional promotional variants were not multiplied into every language. Their language-specific release dates remain unknown where not evidenced.

Provisional records identify a known card but lack adequate physical printing detail. They remain in the binder with a warning, but cannot become Owned/Ordered or generate a recommendation until documented. Resolving a provisional base retires its placeholder non-destructively. TCGdex discovery imports remain provisional and never override a documented identity. Discoveries for already documented bases are retained for manual review rather than silently replacing them.

The GameStop 151 finish has differing source descriptions and is provisional. Mirage Obsidian Flames, stamped and unstamped Cosmos Parallel 151 releases are separately distinguished; generic reverse-holo is not an interchangeable slab. Some card images can depict generic reference artwork rather than a particular finish or stamp; they are never certification evidence.

## Known gaps

The seed is not a complete edition/release/foil/stamp census. It is especially incomplete for Korean, Simplified/Traditional Chinese, Indonesian, Thai and additional regional languages; some have no bundled records. There is no audited artwork-cameo list. Trainer-associated and Delta Species entries are included where known but mostly unresolved. Special, jumbo, event and retailer releases need further review. Dutch is not currently a selectable language. New releases require continuing catalogue research. Automatic discovery is bounded (30 base cards per invocation); a completed provider pass does not establish worldwide completeness.

PSA 10 population and availability are unknown unless a genuine owned record or reviewed listing provides evidence. No PSA population API or certification verification API is connected. Empty listing results never remove catalogue cards.


## Source capability inventory — reviewed 10 October 2026

| Source | Access and delivered adapter | Coverage / limits / activation |
|---|---|---|
| TCGdex catalogue | Official no-key REST, 30-card discovery batches | Source-linked provisional cards; no worldwide completeness assertion. Network needed. |
| eBay listings | Official production OAuth and Browse API | Active offers and current bids; configured regional marketplace, up to 10 exact variants/run, <=50 results/query and <=10 direct item checks. Requires eligible production access. Not a sold-history API. |
| Cardmarket / TCGplayer guides via TCGdex | Documented no-key card `pricing` object | Aggregate standard/holo/provider categories, EUR/USD and provider update date; no individual seller/delivery/condition-specific transactions. Explicit card refresh, 24-hour cache, >=2s global interval, 2MB response cap. |
| Cardmarket direct | Manual exact listings/sales and research link | New listing API applications are closed. **Official daily public catalogue/guide exports are separately available**; this release accesses contextual guides via TCGdex rather than scraping offers or downloading the bulk export. Cardmarket scales remain distinct. |
| TCGplayer direct | Manual source-linked listings/sales and research link | New API grants unavailable according to its documentation; existing license/terms needed for a direct integration. This app does not imply direct authorized listing access. |
| PriceCharting | Optional official **Prices API** read-only product adapter | Existing licensed token; owner-confirmed product ID; USD cents converted to dollar values; >=2s and 24h product cache. Current group estimates only, not completed transactions. Prices API does not supply historical prices/sales. Its separate Marketplace API is **not implemented** here. |
| Specialist dealers / auction archives | Exact manual entry / validated CSV | Actual source, title, condition, transaction date and disclosed price; review assertions are not independently authenticated. No automatic cross-site crawl. |
| Frankfurter FX | Dated reference rates | Missing or >7-day-old conversions do not support totals. Not historical-sale-day FX. |
| PSA/BGS/CGC evidence | Owner review of photos, label, cert and identity | No automatic grading-company API, certificate authenticity, photo interpretation or population feed. |

Manual entries, external searches, a guide request and a completed listing scan are separately labelled. Failed/blocked sources do not imply unavailable cards. “Best” means among scanned/recorded eligible offers, not all Internet inventory. There is no price or ownership demonstration data in the initial database.

## Primary source documentation

Provider statements checked through their own documentation; no third-party scraper service is assumed authorized.

- TCGdex market fields, cadence and omitted-provider semantics: https://tcgdex.dev/markets-prices
- TCGdex card response / categories: https://tcgdex.dev/reference/card
- eBay Browse: https://developer.ebay.com/api-docs/buy/static/api-browse.html
- eBay production requirements: https://developer.ebay.com/api-docs/buy/static/buy-requirements.html
- Cardmarket new API applications: https://help.cardmarket.com/en/cardmarket-api
- Cardmarket public guide release: https://news.cardmarket.com/en/Magic/were-making-the-price-guide-and-product-catalogue-available-for-download
- Cardmarket public exports and integration permission: https://insight.cardmarket.com/en/Articles/whats-new-on-cardmarket-7-2025
- TCGplayer access restrictions: https://docs.tcgplayer.com/docs/getting-started
- PriceCharting Prices versus Marketplace APIs, grade groups, internal-use/cache restrictions: https://www.pricecharting.com/api-documentation

A direct no-key TCGdex API request in this environment failed DNS resolution. Its documented adapter passed mock contract tests but no live guide prices were obtained. eBay/PriceCharting authorized live calls were not possible without credentials. Current guides in a future user installation can still be stale; provider update date and actual observation date are both shown, with neither presented as a sale date.

## Catalogue reference pages

- https://github.com/tcgdex/cards-database/blob/master/data/Base/Base%20Set/46.ts
- https://github.com/tcgdex/cards-database/blob/master/data/Scarlet%20%26%20Violet/Obsidian%20Flames/026.ts
- https://github.com/tcgdex/cards-database/blob/master/data/Scarlet%20%26%20Violet/151/004.ts
- https://bulbapedia.bulbagarden.net/wiki/Charmander_(TCG)
- https://bulbapedia.bulbagarden.net/wiki/Charmander_(Obsidian_Flames_26)
- https://bulbapedia.bulbagarden.net/wiki/Charmander_(151_4)

The seed and catalogue assertions are retained from the inspected 2.0 archive; the update did not claim a newly audited worldwide list. Community catalogue documentation is not a first-party certification of completeness.
