"""Supported, bounded official APIs. No scraping or automatic purchasing."""
from datetime import datetime, timezone
import base64
import hashlib
import json
import math
import time
import httpx
from .db import now, dumps
from .models import canonical_url, public_url
from .security import decrypt, encrypt
from .matching import screen
from .conditions import infer_condition, condition_key
from .observations import snapshot_listing


class SourceError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class Ebay:
    def __init__(self, client, credentials):
        self.client, self.credentials = client, credentials
        self.token, self.expiry = "", 0

    async def authorize(self):
        if self.token and self.expiry > time.time() + 30:
            return
        basic = base64.b64encode((self.credentials["client_id"]+":"+self.credentials["client_secret"]).encode()).decode()
        try:
            r = await self.client.post("https://api.ebay.com/identity/v1/oauth2/token",
                headers={"Authorization":"Basic "+basic,"Content-Type":"application/x-www-form-urlencoded"},
                data={"grant_type":"client_credentials","scope":"https://api.ebay.com/oauth/api_scope"})
            if r.status_code != 200:
                raise SourceError("credential_error", f"eBay OAuth returned HTTP {r.status_code}. Eligible production credentials are required.")
            payload=r.json(); self.token=payload["access_token"]; self.expiry=time.time()+min(int(payload.get("expires_in",7200)),7200)
        except httpx.HTTPError:
            raise SourceError("connection_error", "Cannot reach the eBay OAuth endpoint.") from None
        except (ValueError, KeyError, TypeError):
            raise SourceError("provider_error", "Unexpected eBay OAuth response.") from None

    def headers(self, prefs):
        return {"Authorization": "Bearer "+self.token, "X-EBAY-C-MARKETPLACE-ID": prefs["ebay_marketplace"],
                "X-EBAY-C-ENDUSERCTX": "contextualLocation=country%3D"+prefs["country"]}

    async def search(self, query, prefs):
        await self.authorize()
        try:
            r=await self.client.get("https://api.ebay.com/buy/browse/v1/item_summary/search", headers=self.headers(prefs),
                params={"q":query[:100],"limit":50,"filter":"buyingOptions:{FIXED_PRICE|AUCTION}","category_ids":"183454"})
            if r.status_code != 200:
                raise SourceError("rate_limited" if r.status_code==429 else "access_error", f"eBay Browse returned HTTP {r.status_code}; no complete scan can be claimed.")
            body=r.json()
            return body.get("itemSummaries",[])[:50], max(int(body.get("total",0)),len(body.get("itemSummaries",[])))
        except httpx.HTTPError:
            raise SourceError("connection_error", "eBay Browse request failed; existing records preserved.") from None
        except (ValueError, TypeError):
            raise SourceError("provider_error", "Unexpected eBay search response.") from None

    async def detail(self, item_id, prefs):
        from urllib.parse import quote
        await self.authorize()
        try:
            r=await self.client.get("https://api.ebay.com/buy/browse/v1/item/"+quote(item_id,safe=""),headers=self.headers(prefs))
            if r.status_code in {404,410}:
                return None
            if r.status_code!=200:
                raise SourceError("access_error", f"eBay item check returned HTTP {r.status_code}.")
            return r.json()
        except httpx.HTTPError:
            raise SourceError("connection_error", "eBay item refresh failed.") from None


def normalize_ebay(item, prefs):
    options=item.get("buyingOptions",[])
    auction="AUCTION" in options
    price=item.get("currentBidPrice") if auction else item.get("price")
    if not price or "value" not in price:
        return None
    try:
        amount=float(price["value"])
        if not math.isfinite(amount) or amount < 0 or amount>100_000_000:
            return None
        url=canonical_url(item.get("itemWebUrl", ""))
        if not url:
            return None
        shipping_values=[]
        for option in item.get("shippingOptions",[]):
            p=option.get("shippingCost",{})
            if p.get("currency")==price["currency"] and p.get("value") is not None:
                try: candidate=float(p["value"])
                except (ValueError,TypeError): continue
                if math.isfinite(candidate) and 0<=candidate<=100_000_000:
                    shipping_values.append(candidate)
        shipping=min(shipping_values) if shipping_values else None
        aspects={a["name"]:a["value"] for a in item.get("localizedAspects",[]) if "name" in a and "value" in a}
        cert=next((v for k,v in aspects.items() if "certification number" in k.lower()), "")
        raw_condition=item.get("conditionDescription") or item.get("condition", "")
        condition=infer_condition(item["title"],raw_condition,"eBay",aspects)
        availability=[a.get("estimatedAvailabilityStatus","") for a in item.get("estimatedAvailabilities",[])]
        status="unavailable" if "OUT_OF_STOCK" in availability else "active"
        delivery=True if shipping is not None else None
        excluded=item.get("shipToLocations",{}).get("regionExcluded",[])
        if any(r.get("regionName")==prefs["country"] for r in excluded): delivery=False
        feedback=item.get("seller",{}).get("feedbackPercentage")
        try: feedback=float(feedback) if feedback is not None else None
        except (ValueError,TypeError): feedback=None
        if feedback is not None and (not math.isfinite(feedback) or not 0<=feedback<=100): feedback=None
        return {**condition,"id":"listing_"+hashlib.sha256(url.encode()).hexdigest()[:24],"source_id":url,
            "provider_id":item["itemId"],"title":item["title"],"url":url,"image_url":public_url(item.get("image",{}).get("imageUrl","")),
            "source":"eBay", "seller":item.get("seller",{}).get("username", ""),
            "seller_feedback":feedback,"seller_country":item.get("itemLocation",{}).get("country",""),"delivery_eligible":delivery,"price":amount,"currency":price["currency"],
            "shipping":shipping,"fees":None,"import_cost":None,"destination_country":prefs["country"],
            "listing_type":"auction" if auction else "fixed", "end_at":item.get("itemEndDate", ""),
            "cert":cert,"aspects":aspects,"status":status,"checked_at":now(),"notes":"",
            "verification_origin":"Official eBay Browse API; not a photograph/certification verification"}
    except (ValueError, KeyError, TypeError):
        return None


def save_listing(db, listing, variant):
    matched=screen(listing["title"], variant, listing.get("aspects"),listing)
    with db.connect() as c:
        old=c.execute("SELECT data FROM listings WHERE id=?", (listing["id"],)).fetchone()
        if old:
            old=json.loads(old[0])
            listing["notes"]=old.get("notes","")
            for field in ["fees","import_cost"]:
                unchanged_cost_basis=all(old.get(k)==listing.get(k) for k in ["destination_country","currency","price","shipping"])
                if unchanged_cost_basis:
                    listing[field]=old.get(field)
            # Source edit invalidates verification. Price-only change does not change identity.
            unchanged=all(old.get(k)==listing.get(k) for k in ["title","image_url","cert","aspects","grader","grade","designation","grading_scale","raw_condition","condition_scale","condition_original"])
            if not unchanged:
                for prior in c.execute("SELECT variant_id,data FROM listing_matches WHERE listing_id=?",(listing["id"],)).fetchall():
                    m=json.loads(prior["data"])
                    m.update(status="candidate",confidence="unverified",notes="Source identity changed; re-review required.")
                    c.execute("UPDATE listing_matches SET data=? WHERE listing_id=? AND variant_id=?",(dumps(m),listing["id"],prior["variant_id"]))
            previous=c.execute("SELECT data FROM listing_matches WHERE listing_id=? AND variant_id=?", (listing["id"],variant["id"])).fetchone()
            if unchanged and previous and matched["status"]!="rejected":
                prev=json.loads(previous[0])
                if prev.get("status")=="verified":
                    matched=prev
        c.execute("INSERT INTO listings VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,checked_at=excluded.checked_at",(listing["id"],listing["source_id"],dumps(listing),listing["checked_at"]))
        c.execute("INSERT INTO listing_matches VALUES(?,?,?) ON CONFLICT(listing_id,variant_id) DO UPDATE SET data=excluded.data",(listing["id"],variant["id"],dumps(matched)))
        snapshot_listing(c,listing)
    return matched


async def refresh_fx(db, client=None):
    own=client is None
    client=client or httpx.AsyncClient(timeout=12,follow_redirects=False)
    try:
        r=await client.get("https://api.frankfurter.dev/v1/latest",params={"base":"EUR","symbols":"USD,GBP,JPY,CHF,CAD,AUD"})
        r.raise_for_status(); x=r.json()
        rates=x["rates"]; rates["EUR"]=1.0
        if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in rates.values()):
            raise ValueError("Invalid exchange rates")
        result={"date":x["date"],"rates":rates,"source":"Frankfurter v1 / European Central Bank reference rates","source_url":"https://api.frankfurter.dev/v1/latest?base=EUR","checked_at":now()}
        db.put("fx",result); db.put("fx_status",{"status":"ok","checked_at":now()})
        return result
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        result={"status":"connection_error","checked_at":now(),"message":"Exchange-rate refresh failed. Same-currency calculations still work; missing/stale conversions remain unknown."}
        db.put("fx_status",result)
        return result
    finally:
        if own:
            await client.aclose()


def load_credentials(db, config):
    value=db.get("ebay_credentials")
    if not value:
        raise SourceError("missing_credentials", "Connect eligible eBay production credentials in Settings. No marketplace scan was performed.")
    try:
        return json.loads(decrypt(config,value))
    except Exception:
        raise SourceError("credential_error", "Stored credentials cannot be decrypted; reconnect in Settings using the deployment encryption key.") from None


async def connect_ebay(db, config, credentials, prefs, client=None):
    own=client is None
    client=client or httpx.AsyncClient(timeout=12,follow_redirects=False)
    try:
        ebay=Ebay(client,credentials)
        await ebay.search("Charmander PSA 10",prefs)
        db.put("ebay_credentials", encrypt(config,dumps(credentials)))
        db.put("last_scan_attempt",None)
        result={"status":"connected","checked_at":now(),"message":"Production OAuth and Browse access verified. Listing identity still requires slab review."}
        db.put("ebay_status",result)
        return result
    except SourceError as e:
        result={"status":e.status,"checked_at":now(),"message":e.message}
        db.put("ebay_status",result)
        return result
    finally:
        if own:
            await client.aclose()
