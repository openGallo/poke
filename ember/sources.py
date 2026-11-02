"""Capability inventory: no unsupported marketplace is advertised as a live feed."""
from urllib.parse import urlencode

SOURCE_CAPABILITIES = [
 {"id":"tcgdex_guides","name":"Cardmarket / TCGplayer public guides via TCGdex","access":"Documented no-key TCGdex card API; owner-confirmed base-card mapping","data":"Aggregate guide metrics only; not individual listings or completed sales","coverage":"Returned provider groups preserved; condition/language/printing may be mixed","requirements":"No account or token; public API must be reachable","frequency":"Explicit per-card refresh; 24-hour cache; >=2 seconds globally","limitations":"Excluded from valuations and bargains. Not proof of seller availability, exact-condition value or a successful marketplace scan","docs":"https://tcgdex.dev/markets-prices"},
 {"id":"ebay","name":"eBay","access":"Official OAuth + Browse API","data":"Active fixed-price listings and auction bids; not completed sales","coverage":"Configured regional marketplace, seller delivery and language evidence vary","requirements":"Eligible production Buy API credentials and permissions","frequency":"Bounded batches, saved owner interval; rate-limit errors surfaced","limitations":"Photographs/certification require owner review; query caps may omit listings","docs":"https://developer.ebay.com/api-docs/buy/static/api-browse.html"},
 {"id":"cardmarket","name":"Cardmarket","access":"Source-linked manual entry / CSV; external search","data":"Manual listing or sale evidence only; public guide is aggregate context","coverage":"European marketplace; its condition scale is retained","requirements":"New listing API applications closed; public daily aggregate exports are separately available without API credentials","frequency":"No automatic listing scanning; guides available separately via TCGdex","limitations":"Not a scanned listing source. EX/GD/LP labels are not equivalent to another platform's grades","docs":"https://help.cardmarket.com/en/cardmarket-api"},
 {"id":"tcgplayer","name":"TCGplayer","access":"Source-linked manual entry / CSV; external search","data":"Manual listing or completed-sale evidence","coverage":"Primarily US marketplace; verify languages and shipping for each offer","requirements":"New API access not granted; access and reuse subject to provider terms","frequency":"No automatic scanning implemented","limitations":"Not a scanned source. No assumed graded-sales history feed","docs":"https://docs.tcgplayer.com/docs/getting-started"},
 {"id":"pricecharting","name":"PriceCharting","access":"Optional official Prices API, read-only","data":"Current aggregate estimates ONLY, not historical transactions","coverage":"Owner-confirmed exact product mapping; source grade groups preserved","requirements":"Existing licensed API subscription/token; no purchase or subscription activation","frequency":"Manual per-product refresh, >=2 seconds globally, 24-hour product cache","limitations":"Never used as completed-sale evidence or a bargain label; purge cached values if subscription ends","docs":"https://www.pricecharting.com/api-documentation"},
 {"id":"manual","name":"Specialist dealers and auction archives","access":"Owner-entered source links or CSV","data":"Exact-copy listings; disclosed completed transactions","coverage":"Any legitimate public HTTPS source with documented exact identity","requirements":"Owner must have permission to use evidence; no paywall or bot-control bypass","frequency":"Owner updates and timestamps; no automatic crawl","limitations":"Owner assertions, not independently authenticated sales; disappearance does not prove sale","docs":""},
]


def source_inventory(db):
    out=[]
    for entry in SOURCE_CAPABILITIES:
        x=dict(entry)
        state=db.get(entry['id']+'_status')
        x['state']=state or {'status':'missing_credentials' if entry['id'] in {'ebay','pricecharting'} else ('not_checked' if entry['id']=='tcgdex_guides' else 'manual_only'),'message':entry['requirements']}
        out.append(x)
    return out


def research_links(v):
    # Navigational search links only; they are not offers, prices or completed scans.
    q=f'{v["name"]} {v["number"]} {v["set_name"]} {v["language"]}'
    return [
        {'source':'eBay · PSA 10','url':'https://www.ebay.com/sch/i.html?'+urlencode({'_nkw':q+' PSA 10'}),'type':'external_search'},
        {'source':'eBay · all conditions','url':'https://www.ebay.com/sch/i.html?'+urlencode({'_nkw':q}),'type':'external_search'},
        {'source':'Cardmarket','url':'https://www.cardmarket.com/en/Pokemon/Products/Search?'+urlencode({'searchString':v['name']+' '+v['number'].split('/')[0]}),'type':'external_search'},
        {'source':'TCGplayer','url':'https://www.tcgplayer.com/search/pokemon/product?'+urlencode({'productLineName':'pokemon','q':q,'view':'grid'}),'type':'external_search'},
        {'source':'PriceCharting','url':'https://www.pricecharting.com/search-products?'+urlencode({'q':q,'type':'prices'}),'type':'external_search'},
    ]
