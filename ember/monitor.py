"""Bounded scheduler with DB leases, persisted executions, and idempotent in-app alerts."""
import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import json
import uuid
import httpx
from .db import now, dumps
from .models import Preferences
from .catalogue import in_scope
from .providers import Ebay, SourceError, load_credentials, normalize_ebay, save_listing
from .pricing import valuation, assess, budget_state, convert
from .conditions import (is_psa10, condition_key, condition_label, cert_identity,
                         need_listing, target_for, preference_keys)


def evaluate_alerts(db):
    prefs=Preferences.model_validate(db.get("preferences",{})).model_dump()
    if prefs["paused"] or not prefs["notifications"]:
        return 0
    fx=db.get("fx")
    copies=db.records("copies")
    owned={c["variant_id"] for c in copies if c["status"] in {"Owned","Ordered"} and is_psa10(c)}
    watch={w["variant_id"]:w for w in db.records("watchlist")}
    variants={v["id"]:v for v in db.records("variants")}
    sales=db.records("sales")
    listings={l["id"]:l for l in db.records("listings")}
    budget=budget_state(copies,prefs,fx)
    candidates=[]
    for row in db.rows("SELECT * FROM listing_matches"):
        vid=row["variant_id"]; v=variants.get(vid); l=listings[row["listing_id"]]
        if not v or not in_scope(v,prefs) or vid in owned:
            continue
        if prefs["monitor_mode"]=="watchlist" and vid not in watch:
            continue
        if not need_listing(vid,l,copies,prefs,watch.get(vid)):
            continue
        match=json.loads(row["data"])
        a=assess(l,match,valuation(vid,sales,prefs,fx,condition=l),prefs,fx,budget)
        target=target_for(l,watch.get(vid),prefs)
        converted_target=convert(target,watch.get(vid,{}).get("currency",prefs["currency"]),prefs["currency"],fx)
        hit_target=a["eligible_for_target"] and converted_target is not None and a["cost"]["total"]<=converted_target
        hit_bargain=a["label"]=="Good buying opportunity" and a["within_budget"]
        if not hit_target and not hit_bargain:
            continue
        reason="Below your target price (not necessarily below market value)" if hit_target else a["explanation"]
        physical_id="cert:"+cert_identity(l,match["cert"]) if match.get("cert") else "listing:"+l["id"]
        fingerprint=hashlib.sha256(dumps([physical_id,vid,condition_key(l),a["cost"]["total"],prefs["currency"],prefs["country"]]).encode()).hexdigest()
        candidates.append((watch.get(vid,{}).get("priority",1),a["cost"]["total"],fingerprint,{"variant_id":vid,"listing_id":l["id"],"condition_key":condition_key(l),"condition_label":condition_label(l),"condition_confidence":a["condition_confidence"],"name":v["name"],"set_name":v["set_name"],"number":v["number"],"cost":a["cost"],"reason":reason,"match_confidence":a["match_confidence"],"price_confidence":a["price_confidence"],"url":l["url"],"physical_id":physical_id}))
    count=0
    # Individual alerts meet the budget; they are not reservations or a combined shopping basket.
    seen=set()
    for _,_,fp,data in sorted(candidates,key=lambda x:(-x[0],x[1])):
        identity=(data["variant_id"],data["physical_id"])
        if identity in seen:
            continue
        seen.add(identity)
        with db.connect() as c:
            cur=c.execute("INSERT OR IGNORE INTO alerts(id,fingerprint,data,created_at) VALUES(?,?,?,?)",(uuid.uuid4().hex,fp,dumps(data),now()))
            count+=cur.rowcount
    return count


async def run_monitor(db, config, trigger="manual", force=False, client=None, requested_variant=None):
    started=now()
    result={"id":uuid.uuid4().hex,"checkedAt":started,"trigger":trigger,"status":"running","scanned_variants":0,"search_results":0,"rechecked_listings":0,"candidate_matches":0,"rejected_matches":0,"new_alerts":0,"errors":[]}
    lease=db.lease("monitor",900)
    if not lease:
        return {**result,"status":"busy","message":"Another updater holds the scan lease."}
    own=client is None
    client=client or httpx.AsyncClient(timeout=12,follow_redirects=False)
    try:
        prefs=Preferences.model_validate(db.get("preferences",{})).model_dump()
        last=db.get("last_scan_attempt")
        elapsed=float("inf")
        if last:
            elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(last)).total_seconds()
        if prefs["paused"]:
            result.update(status="paused",message="Saved pause state honored. No marketplace request sent.")
        elif not force and elapsed<prefs["refresh_hours"]*3600:
            result.update(status="not_due",message="Saved refresh interval has not elapsed.")
        else:
            db.put("last_scan_attempt",started)
            credentials=load_credentials(db,config)
            ebay=Ebay(client,credentials)
            copies=db.records("copies")
            collected={c["variant_id"] for c in copies if c["status"] in {"Owned","Ordered"} and is_psa10(c)}
            watch={w["variant_id"]:w for w in db.records("watchlist")}
            vs=[v for v in db.records("variants") if in_scope(v,prefs) and v["id"] not in collected and v["identity_status"]=="documented" and (prefs["monitor_mode"]=="missing" or v["id"] in watch)]
            if requested_variant is not None:
                vs=[v for v in vs if v["id"]==requested_variant]
            vs.sort(key=lambda v:(-watch.get(v["id"],{}).get("priority",1),v["id"]))
            cursor=db.get("monitor_cursor",0)%max(1,len(vs))
            batch=(vs[cursor:]+vs[:cursor])[:10]
            result.update(eligible_variants=len(vs),batch_size=len(batch),cursor=cursor,coverage="Rotating batch: at most 10 exact variants, two queries per variant and 50 results per query. Search absence does not imply sale or unavailability.")
            truncated=False
            for v in batch:
                base_query=f'{v["name"]} {v["number"].split("/")[0]} {v["set_name"]}'
                queries=[base_query+" PSA 10"]
                if len(preference_keys(prefs,watch.get(v["id"])))>1:
                    queries.append(base_query)  # Raw and other grades; never a PSA-10-only filter.
                seen_ids=set(); count=0; variant_truncated=False
                for query in queries:
                    items,total=await ebay.search(query,prefs)
                    variant_truncated|=total>len(items)
                    for item in items:
                        l=normalize_ebay(item,prefs)
                        if not l or l["id"] in seen_ids: continue
                        seen_ids.add(l["id"]); count+=1
                        m=save_listing(db,l,v)
                        result["rejected_matches" if m["status"]=="rejected" else "candidate_matches"]+=1
                truncated|=variant_truncated
                result["scanned_variants"]+=1
                result["search_results"]+=count
                db.put("scan_coverage:"+v["id"],{"checked_at":now(),"source":"eBay","queries":queries,
                    "results":count,"truncated":variant_truncated,"includes_fallbacks":len(queries)>1,
                    "country":prefs["country"],"marketplace":prefs["ebay_marketplace"],
                    "message":"Search candidates only; no-listing result is limited to this bounded source scan."})
                if requested_variant is None:
                    db.put("monitor_cursor",(cursor+result["scanned_variants"])%max(1,len(vs)))
            # Directly verify old records, never infer sold from search omissions.
            eligible_ids={v["id"] for v in vs}
            linked_ids={row["listing_id"] for row in db.rows("SELECT listing_id,variant_id FROM listing_matches") if row["variant_id"] in eligible_ids}
            old=[l for l in db.records("listings") if l["id"] in linked_ids and l.get("source")=="eBay" and l.get("provider_id") and l.get("status")=="active"]
            old.sort(key=lambda l:l["checked_at"])
            for l in old[:10]:
                item=await ebay.detail(l["provider_id"],prefs)
                result["rechecked_listings"]+=1
                if item is None:
                    l.update(status="unavailable",checked_at=now(),unavailable_reason="Item endpoint returned 404/410; sale not established.")
                    with db.connect() as c:
                        c.execute("UPDATE listings SET data=?,checked_at=? WHERE id=?",(dumps(l),l["checked_at"],l["id"]))
                else:
                    fresh=normalize_ebay(item,prefs)
                    if fresh:
                        for row in db.rows("SELECT variant_id FROM listing_matches WHERE listing_id=?",(l["id"],)):
                            found=next((v for v in db.records("variants") if v["id"]==row["variant_id"]),None)
                            if found:
                                save_listing(db,fresh,found)
            result["new_alerts"]=evaluate_alerts(db)
            result["status"]="partial" if truncated or len(batch)<len(vs) else "completed"
            result["search_truncated"]=truncated
            result["message"]="Bounded marketplace scan completed. All new results require exact-identity and condition/grade review."
            if not batch and not old:
                result.update(status="no_eligible_cards",message="No missing, documented variants matched the saved scope. No marketplace request sent.")
            else:
                db.put("ebay_status",{"status":"connected","checked_at":now(),"message":"Last bounded Browse scan succeeded."})
    except asyncio.CancelledError:
        result.update(status="cancelled",message="Updater interrupted; existing data retained and scan coverage incomplete.")
        raise
    except SourceError as e:
        result.update(status=e.status,message=e.message)
        result["errors"].append(e.message)
        db.put("ebay_status",{"status":e.status,"checked_at":now(),"message":e.message})
    except Exception:
        # Never reflect provider payloads, tokens or exception strings into the UI/logs.
        result.update(status="error",message="Updater failed unexpectedly. Existing collection data preserved; inspect application diagnostics.")
        result["errors"].append("Unexpected updater error")
    finally:
        if own:
            await client.aclose()
        result["finishedAt"]=now()
        db.put("monitor_heartbeat",result)
        with db.connect() as c:
            c.execute("INSERT INTO scan_log VALUES(?,?,?)",(result["id"],started,dumps(result)))
            c.execute("DELETE FROM scan_log WHERE id NOT IN (SELECT id FROM scan_log ORDER BY time DESC LIMIT 100)")
        db.release("monitor",lease)
    return result


async def scheduler_loop(db,config):
    """Persist scheduler health independently of successful marketplace coverage."""
    while True:
        db.put("scheduler_state",{"state":"waiting","updated_at":now(),
            "next_wake_at":(datetime.now(timezone.utc)+timedelta(seconds=config.tick_seconds)).isoformat()})
        await asyncio.sleep(config.tick_seconds)
        db.put("scheduler_state",{"state":"running","updated_at":now()})
        try:
            result=await run_monitor(db,config,trigger="scheduled",force=False)
            db.put("scheduler_last_result",{"checkedAt":result["checkedAt"],"status":result["status"]})
        except Exception:
            # Keep the scheduler alive; never log provider credentials or raw payloads.
            db.put("scheduler_last_result",{"checkedAt":now(),"status":"scheduler_error"})
            db.activity("Scheduled updater failed outside the scan handler; it will retry at the next wake.")
