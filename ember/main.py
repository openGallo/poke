"""Owner-only FastAPI application. Run through `python -m ember serve`."""
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import secrets
import re
import sqlite3
import uuid
import threading
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from PIL import Image, UnidentifiedImageError

from .config import Config, ROOT
from .db import DB, now, dumps
from . import __version__
from .models import (Preferences, Variant, CopyIn, WatchIn, ListingIn, SaleIn, MatchReview,
                     CredentialsIn, ImportIn, LoginIn, SetupIn, SavedSearchIn, LANGUAGES, CURRENCIES, canonical_url, PriceChartingCredentials, AggregateRequest, PublicGuideRequest)
from . import security
from .catalogue import seed, store_variant, in_scope, GAPS, sync_language
from .matching import screen
from .pricing import valuation, assess, budget_state
from .providers import connect_ebay, refresh_fx
from .monitor import run_monitor, scheduler_loop, evaluate_alerts
from .conditions import (is_psa10, condition_key, condition_label, condition_known, condition_data,
                         cert_identity, allowed_condition, need_listing, bucket_options)
from .buying import comparison, rank_deals
from .sources import source_inventory, research_links
from .observations import snapshot_listing, history_for
from . import aggregates, public_guides
from .providers import SourceError

IMPORT_MODELS={"copies":CopyIn,"sales":SaleIn,"listings":ListingIn,"watchlist":WatchIn}
COOKIE="ember_session"


def create_app(config: Config | None = None):
    config=config or Config.load()
    db=DB(config.data_dir/"ember.sqlite3")
    seed(db)
    if db.get("preferences") is None:
        db.put("preferences",Preferences().model_dump())

    @asynccontextmanager
    async def lifespan(app):
        task=asyncio.create_task(scheduler_loop(db,config)) if config.scheduler else None
        app.state.scheduler_task=task
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app=FastAPI(title="Ember",version=__version__,docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.db=db; app.state.config=config
    setup_lock=threading.Lock()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path=request.url.path
        origin=request.headers.get("origin")
        try:
            hostname=(urlsplit("//"+request.headers.get("host","")).hostname or "").lower()
        except ValueError:
            return JSONResponse({"detail":"Invalid host"},400)
        expected=(urlsplit(config.origin).hostname or "").lower()
        if hostname != expected:
            return JSONResponse({"detail":"Unrecognized host"},400)
        if request.method not in {"GET","HEAD","OPTIONS"}:
            if origin and origin!=config.origin:
                return JSONResponse({"detail":"Cross-origin write rejected"},403)
            body=bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body)>6_000_000:
                    return JSONResponse({"detail":"Request too large"},413)
            request._body=bytes(body)
        public=path in {"/","/healthz","/api/login","/api/bootstrap","/api/setup"} or path.startswith("/static/")
        request.state.owner=False
        request.state.csrf=""
        if not public:
            is_service=False
            if path=="/api/monitor" and config.monitor_token:
                bearer=request.headers.get("authorization","")
                is_service=secrets.compare_digest(bearer,"Bearer "+config.monitor_token)
            auth=security.session(db,config,request.cookies.get(COOKIE,""))
            if not auth and not is_service:
                return JSONResponse({"detail":"Sign in to access your private collection."},401)
            if auth:
                request.state.owner=True; request.state.csrf=auth["csrf"]
            if request.method not in {"GET","HEAD","OPTIONS"} and not is_service:
                if not secrets.compare_digest(request.headers.get("x-csrf-token",""),auth["csrf"]):
                    return JSONResponse({"detail":"CSRF token missing or invalid"},403)
        response=await call_next(request)
        response.headers.update({"X-Content-Type-Options":"nosniff", "X-Frame-Options":"DENY",
            "Referrer-Policy":"no-referrer", "Permissions-Policy":"camera=(), microphone=(), geolocation=()",
            "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' https: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"})
        if path.startswith("/api") or path.startswith("/photos"):
            response.headers["Cache-Control"]="no-store, private"
        if config.secure:
            response.headers["Strict-Transport-Security"]="max-age=31536000"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic includes supplied input by default; do not reflect secrets or whole uploads.
        errors=[{"field":".".join(str(x) for x in e["loc"]),"message":e["msg"]} for e in error.errors()]
        return JSONResponse({"detail":"Invalid input","errors":errors},422)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(request,error):
        return JSONResponse({"detail":"Duplicate certification, duplicate evidence, or invalid record reference. No partial changes saved."},409)

    app.mount("/static",StaticFiles(directory=ROOT/"static"),name="static")

    @app.get("/")
    def home():
        return FileResponse(ROOT/"static/index.html")

    @app.get("/healthz")
    def health():
        db.rows("SELECT 1")
        return {"status":"ok","version":__version__}

    @app.get("/api/bootstrap")
    def bootstrap():
        return {"setup_required": config.setup_required, "desktop": config.desktop,
                "version": __version__, "monitoring": "Scans run while Ember is open and monitoring is enabled. macOS sleep pauses network work."}

    @app.post("/api/setup")
    def first_run(payload: SetupIn):
        nonlocal config
        with setup_lock:
            if not config.desktop or not config.setup_required:
                raise HTTPException(409, "This installation is already configured. Use your existing owner password.")
            from .desktop import write_configuration
            new=replace(config, password_hash=security.PH.hash(payload.password), setup_required=False)
            write_configuration(config.data_dir/"config.json", {
                "password_hash": new.password_hash, "encryption_key": new.encryption_key,
                "monitor_token": new.monitor_token, "public_url": "http://127.0.0.1:8000", "setup_required": False})
            config=new
            app.state.config=new
            return {"ok": True}

    @app.get("/api/backup")
    def download_backup():
        from .backup import backup_bytes
        return Response(backup_bytes(config), media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="ember-private-backup-'+datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")+'.zip"'})

    @app.post("/api/login")
    def sign_in(payload: LoginIn,request:Request):
        ip=request.client.host if request.client else "unknown"
        auth,error=security.login(db,config,payload.password,ip)
        if error:
            return JSONResponse({"detail":"Too many attempts; retry after 15 minutes." if error=="rate_limited" else "Incorrect password."},429 if error=="rate_limited" else 401)
        response=JSONResponse({"csrf":auth["csrf"]})
        response.set_cookie(COOKIE,auth["token"],max_age=86400,httponly=True,secure=config.secure,samesite="strict",path="/")
        return response

    @app.post("/api/logout")
    def sign_out(request:Request):
        with db.connect() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?",(security.digest(request.cookies.get(COOKIE,"")),))
        response=JSONResponse({"ok":True}); response.delete_cookie(COOKIE,path="/")
        return response

    def prefs():
        return Preferences.model_validate(db.get("preferences",{})).model_dump()

    def variant(vid, resolved=False):
        rows=db.rows("SELECT data FROM variants WHERE id=?",(vid,))
        if not rows:
            raise HTTPException(404,"Card not found")
        v=json.loads(rows[0]["data"])
        if resolved and (v["identity_status"]!="documented" or v.get("retired")):
            raise HTTPException(422,"Resolve the exact printing with catalogue evidence before recording ownership or reviewing a listing.")
        return v

    def card_details(vid):
        v=variant(vid); p=prefs()
        d=comparison(db,vid,p)
        siblings=[json.loads(r["data"]) for r in db.rows("SELECT data FROM variants WHERE base_id=?",(v["base_id"],))]
        agg=[json.loads(r['data']) for r in db.rows('SELECT data FROM aggregates WHERE variant_id=?',(vid,))]
        return {**d,"card":v,"variants":siblings,"price_observations":history_for(db,vid),
                "aggregate_observations":agg,"research_links":research_links(v),"source_inventory":source_inventory(db)}

    def all_deals():
        p=prefs(); copies=db.records("copies"); watches={w['variant_id']:w for w in db.records('watchlist')}
        ids={r['variant_id'] for r in db.rows('SELECT variant_id FROM listing_matches')}; results=[]
        for vid in ids:
            v=variant(vid)
            if not in_scope(v,p): continue
            d=card_details(vid)
            for l in d['listings']:
                if l.get('status')!='active' or not need_listing(vid,l,copies,p,watches.get(vid)): continue
                results.append({'card':v,'listing':l,'priority':watches.get(vid,{}).get('priority',1)})
        return rank_deals(results,p)

    @app.get("/api/state")
    def state(request:Request):
        p=prefs(); vs=db.records("variants"); copies=db.records("copies"); watches=db.records("watchlist")
        watch_map={w['variant_id']:w for w in watches}
        physical={c['variant_id'] for c in copies if c['status']=='Owned'}
        owned={c['variant_id'] for c in copies if c['status']=='Owned' and is_psa10(c)}
        any_owned={c['variant_id'] for c in copies if c['status']=='Owned' and allowed_condition(c,p,watch_map.get(c['variant_id']))}
        ordered={c['variant_id'] for c in copies if c['status']=='Ordered'}
        watched={w['variant_id'] for w in watches}
        scope=[v for v in vs if in_scope(v,p)]
        for v in scope:
            v['status']='Owned' if v['id'] in owned else 'Alternative' if v['id'] in physical else 'Ordered' if v['id'] in ordered else 'Watchlist' if v['id'] in watched else 'Missing'
            v['copies_count']=sum(c['variant_id']==v['id'] for c in copies)
            v['psa10_owned']=v['id'] in owned
            v['any_condition_owned']=v['id'] in any_owned
            v['physical_owned']=v['id'] in physical
            v['psa10_availability']='owned' if v['id'] in owned else 'unknown'
        listing_rows=db.rows("SELECT m.variant_id,m.data,l.data AS listing FROM listing_matches m JOIN listings l ON l.id=m.listing_id")
        availability={}
        for r in listing_rows:
            l=json.loads(r["listing"]); m=json.loads(r["data"])
            if not is_psa10(l) or l.get("status")!="active" or m.get("status")=="rejected":
                continue
            try:
                age=(datetime.now(timezone.utc)-datetime.fromisoformat(l["checked_at"].replace("Z","+00:00"))).total_seconds()/3600
            except ValueError:
                continue
            if l.get("end_at"):
                try:
                    if datetime.fromisoformat(l["end_at"].replace("Z","+00:00"))<=datetime.now(timezone.utc):
                        continue
                except (ValueError,TypeError):
                    continue
            if not 0<=age<=p["stale_hours"]:
                continue
            current=availability.setdefault(r["variant_id"],{"candidate":0,"verified":0,"price":None})
            current["verified" if m.get("status")=="verified" else "candidate"]+=1
            if m.get("status")=="verified" and l["listing_type"]=="fixed" and l["currency"]==p["currency"]:
                current["price"]=min(current["price"] or 10**12,l["price"])
        for v in scope:
            a=availability.get(v["id"],{"candidate":0,"verified":0,"price":None})
            v["availability"]=a
            if a["verified"]:
                v["psa10_availability"]="reviewed listing available"
        groups={}
        for field in ["set_name","language"]:
            group={}
            for v in scope:
                item=group.setdefault(v[field],{"total":0,"owned":0,"any_owned":0,"provisional":0})
                item["total"]+=1; item["owned"]+=v["id"] in owned; item["any_owned"]+=v["id"] in any_owned; item["provisional"]+=v["identity_status"]!="documented"
            groups[field]=group
        return {"csrf":request.state.csrf,"version":__version__,"reconstructed":True,"preferences":p,"variants":scope,
                "copies":copies,"watchlist":watches,"saved_searches":db.get("saved_searches",[]),"desktop":config.desktop,"completion":{"owned":len(owned & {v['id'] for v in scope}),"any_owned":len(any_owned & {v['id'] for v in scope}),"missing_every_condition":len({v['id'] for v in scope}-physical),"upgrade_needed":len((physical-owned) & {v['id'] for v in scope}),"total":len(scope),"base_printings":len({v['base_id'] for v in scope}),"ordered":len(ordered & {v['id'] for v in scope}),"groups":groups},
                "coverage":{"catalogue_total":len([v for v in vs if not v.get('retired')]),"resolved":sum(v['identity_status']=='documented' and not v.get('retired') for v in vs),"languages":sorted({v['language'] for v in vs}),"gaps":GAPS,"seed":db.get('seed_metadata'),"sync":[db.get('catalogue_sync:'+lang) for lang in LANGUAGES if db.get('catalogue_sync:'+lang)]},
                "condition_options":bucket_options(),"source_inventory":source_inventory(db),"sources":{"ebay":db.get("ebay_status",{"status":"missing_credentials","message":"Connect eligible production credentials in Settings."}),"fx":db.get("fx_status",{"status":"not_checked"})},
                "budget":budget_state(copies,p,db.get("fx")),"fx":db.get("fx"),"monitor":db.get("monitor_heartbeat"),"scheduler_enabled":config.scheduler,
                "activity":db.rows("SELECT time,message FROM activity ORDER BY id DESC LIMIT 20"),"alerts_unread":db.rows("SELECT count(*) AS n FROM alerts WHERE read=0")[0]["n"],"languages":LANGUAGES,"currencies":sorted(CURRENCIES)}

    @app.get("/api/cards/{vid}")
    def card(vid:str):
        return card_details(vid)

    @app.get("/api/deals")
    def deals(grader:str="",condition:str="",language:str="",listing_type:str="",seller_country:str="",min_cost:float|None=None,max_cost:float|None=None,evidence:str=""):
        result=all_deals()
        def selected(d):
            l=d['listing']; a=l['assessment']; total=a['cost']['total']
            return (not grader or l.get('grader','PSA')==grader) and (not condition or l['condition_key']==condition) and (not language or d['card']['language']==language) and (not listing_type or l['listing_type']==listing_type) and (not seller_country or l.get('seller_country')==seller_country) and (min_cost is None or total is not None and total>=min_cost) and (max_cost is None or total is not None and total<=max_cost) and (not evidence or a['price_confidence']==evidence)
        return {"deals":[d for d in result if selected(d)],"coverage_label":"Best found among recorded/scanned sources, not the whole internet"}

    @app.get("/api/planner")
    def purchase_planner():
        from .planner import completion_estimate, seller_groups
        return {"estimate": completion_estimate(db, prefs()),
                "seller_groups": seller_groups(all_deals(), prefs(), db.get("fx"), db.records("copies"))}

    @app.post("/api/saved-searches")
    def save_search(payload: SavedSearchIn):
        values=db.get("saved_searches",[])
        if len(values)>=50:
            raise HTTPException(422,"Remove a saved search before adding another (limit 50).")
        entry={"id":uuid.uuid4().hex,"name":payload.name,"filters":payload.filters,"created_at":now()}
        db.put("saved_searches",values+[entry])
        return entry

    @app.delete("/api/saved-searches/{ident}")
    def delete_search(ident: str):
        db.put("saved_searches",[x for x in db.get("saved_searches",[]) if x["id"]!=ident])
        return {"ok":True}

    @app.get("/api/sources")
    def sources(): return {"sources":source_inventory(db)}

    @app.post("/api/cards/{vid}/scan")
    async def scan_card(vid:str):
        variant(vid,True)
        return await run_monitor(db,config,"manual-card",force=True,requested_variant=vid)

    @app.put("/api/settings")
    def settings(payload:Preferences):
        old=prefs(); new=payload.model_dump()
        db.put("preferences",new)
        # Country-specific delivery costs are invalidated, never reused for a different destination.
        if old["country"]!=new["country"]:
            with db.connect() as c:
                for row in c.execute("SELECT id,data FROM listings").fetchall():
                    l=json.loads(row["data"])
                    l.update(shipping=None,fees=None,import_cost=None)
                    c.execute("UPDATE listings SET data=? WHERE id=?",(dumps(l),row["id"]))
        db.activity("Collection preferences saved")
        return {"ok":True,"preferences":new}

    @app.post("/api/catalogue")
    def add_variant(payload:Variant):
        data=payload.model_dump(); data["source_checked_at"]=now()
        store_variant(db,data)
        # Retire an unresolved placeholder only when concrete siblings now exist; no records deleted.
        if data["identity_status"]=="documented":
            with db.connect() as c:
                for r in c.execute("SELECT id,data FROM variants WHERE base_id=?",(data["base_id"],)).fetchall():
                    old=json.loads(r["data"])
                    if old["identity_status"]=="provisional":
                        old["retired"]=True
                        c.execute("UPDATE variants SET data=? WHERE id=?",(dumps(old),r["id"]))
        db.activity("Catalogue printing added with provenance")
        return variant(data["id"])

    @app.post("/api/catalogue/sync/{language}")
    async def sync(language:str):
        if language not in LANGUAGES:
            raise HTTPException(422,"Unsupported language")
        return await sync_language(db,language)

    def save_copy(payload, c, ident=None):
        variant(payload.variant_id,True)
        item=payload.model_dump(mode="json"); item["id"]=ident or uuid.uuid4().hex
        item["created_at"]=now()
        if ident:
            old=c.execute("SELECT data FROM copies WHERE id=?",(ident,)).fetchone()
            if not old:
                raise HTTPException(404,"Copy not found")
            old=json.loads(old[0]); item["created_at"]=old["created_at"]
            if old.get("photo_key"):
                item["photo_key"]=old["photo_key"]
            c.execute("UPDATE copies SET variant_id=?,cert=?,data=? WHERE id=?",(item["variant_id"],cert_identity(item),dumps(item),ident))
        else:
            c.execute("INSERT INTO copies VALUES(?,?,?,?,?)",(item["id"],item["variant_id"],cert_identity(item),dumps(item),item["created_at"]))
        return item

    @app.post("/api/copies")
    def add_copy(payload:CopyIn):
        with db.connect() as c:
            item=save_copy(payload,c)
        db.activity(payload.status+" "+condition_label(item)+" copy recorded")
        return item

    @app.put("/api/copies/{ident}")
    def update_copy(ident:str,payload:CopyIn):
        with db.connect() as c:
            item=save_copy(payload,c,ident)
        db.activity("Ownership record updated: "+condition_label(item))
        return item

    @app.delete("/api/copies/{ident}")
    def delete_copy(ident:str):
        with db.connect() as c:
            row=c.execute("SELECT data FROM copies WHERE id=?",(ident,)).fetchone()
            if not row:
                raise HTTPException(404,"Copy not found")
            old=json.loads(row[0]); c.execute("DELETE FROM copies WHERE id=?",(ident,))
            if old.get("photo_key"):
                c.execute("DELETE FROM images WHERE key=?",(old["photo_key"],))
        db.activity("Ownership record removed")
        return {"ok":True}

    @app.post("/api/copies/{ident}/photo")
    async def upload_photo(ident:str,file:UploadFile=File(...)):
        raw=await file.read(5_000_001)
        if len(raw)>5_000_000:
            raise HTTPException(413,"Photo limit is 5 MB")
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG","PNG","WEBP"} or image.width*image.height>20_000_000:
                    raise ValueError("Unsupported image")
                image.load(); image=image.convert("RGB"); image.thumbnail((1800,2400))
                out=io.BytesIO(); image.save(out,format="JPEG",quality=88)
        except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
            raise HTTPException(422,"Use a valid JPG, PNG or WebP photograph under 20 megapixels.") from None
        with db.connect() as c:
            row=c.execute("SELECT data FROM copies WHERE id=?",(ident,)).fetchone()
            if not row:
                raise HTTPException(404,"Copy not found")
            item=json.loads(row[0]); key=item.get("photo_key") or uuid.uuid4().hex
            c.execute("INSERT INTO images VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET content=excluded.content",(key,out.getvalue(),"image/jpeg"))
            item["photo_key"]=key; c.execute("UPDATE copies SET data=? WHERE id=?",(dumps(item),ident))
        return {"photo_url":"/api/photos/"+key}

    @app.get("/api/photos/{key}")
    def photo(key:str):
        rows=db.rows("SELECT content,content_type FROM images WHERE key=?",(key,))
        if not rows:
            raise HTTPException(404,"Photo not found")
        return Response(rows[0]["content"],media_type=rows[0]["content_type"])

    def save_watch(payload,c):
        variant(payload.variant_id)
        item=payload.model_dump()
        c.execute("INSERT INTO watchlist VALUES(?,?) ON CONFLICT(variant_id) DO UPDATE SET data=excluded.data",(item["variant_id"],dumps(item)))
        return item

    @app.put("/api/watchlist")
    def watch(payload:WatchIn):
        with db.connect() as c:
            item=save_watch(payload,c)
        db.activity("Watchlist target updated"); evaluate_alerts(db)
        return item

    @app.delete("/api/watchlist/{vid}")
    def unwatch(vid:str):
        with db.connect() as c:
            c.execute("DELETE FROM watchlist WHERE variant_id=?",(vid,))
        return {"ok":True}

    def save_manual_listing(payload,c):
        v=variant(payload.variant_id)
        item=payload.model_dump(); item.pop("variant_id")
        url=canonical_url(item["url"])
        ident="listing_"+hashlib.sha256(url.encode()).hexdigest()[:24]
        item.update(id=ident,source_id=url,url=url,status="active",checked_at=now(),verification_origin="Owner-entered source-linked observation; not provider-scraped")
        old=c.execute("SELECT data FROM listings WHERE id=?",(ident,)).fetchone()
        if old:
            prior=json.loads(old[0])
            for key in ["provider_id","aspects"]:
                if key in prior:
                    item[key]=prior[key]
        # Invalidate every prior match, not only the variant currently being edited.
        for prior in c.execute("SELECT variant_id,data FROM listing_matches WHERE listing_id=?", (ident,)).fetchall():
            m=json.loads(prior["data"])
            m.update(status="candidate",confidence="unverified",reasons=[],notes="Observation updated; review required again.")
            c.execute("UPDATE listing_matches SET data=? WHERE listing_id=? AND variant_id=?", (dumps(m),ident,prior["variant_id"]))
        # Manual re-entry is an explicit refreshed observation; review must be redone.
        c.execute("INSERT INTO listings VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,checked_at=excluded.checked_at",(ident,url,dumps(item),item["checked_at"]))
        match=screen(item["title"],v,item.get("aspects"),item)
        c.execute("INSERT INTO listing_matches VALUES(?,?,?) ON CONFLICT(listing_id,variant_id) DO UPDATE SET data=excluded.data",(ident,v["id"],dumps(match)))
        snapshot_listing(c,item)
        return {**item,"match":match}

    @app.post("/api/listings")
    def listing(payload:ListingIn):
        with db.connect() as c:
            result=save_manual_listing(payload,c)
        db.activity("Source-linked listing observation saved")
        return result

    @app.post("/api/listings/{ident}/review")
    def review(ident:str,payload:MatchReview):
        v=variant(payload.variant_id,True)
        rows=db.rows("SELECT data FROM listings WHERE id=?",(ident,))
        if not rows:
            raise HTTPException(404,"Listing not found")
        item=json.loads(rows[0]["data"]); result=screen(item["title"],v,item.get("aspects"),item)
        if result["status"]=="rejected":
            raise HTTPException(422,"Contradictory listing cannot be verified: "+"; ".join(result["reasons"]))
        raw=item.get('grader')=='RAW'
        if not condition_known(item):
            raise HTTPException(422,"Resolve the condition, grade, designation and scale before review.")
        required=[payload.identity_confirmed,payload.photo_checked]
        required+=([payload.condition_checked] if raw else [payload.label_checked,payload.cert_checked,bool(payload.cert)])
        if not all(required):
            raise HTTPException(422,"Identity, photographs and raw-condition checks are required; graded copies also need slab-label and certificate review.")
        if item.get("grader")=="PSA" and not re.fullmatch(r"\d{6,12}",payload.cert):
            raise HTTPException(422,"PSA review requires a 6–12 digit certification number.")
        if raw and payload.cert:
            raise HTTPException(422,"Raw cards cannot have a grading certification number.")
        if item.get("cert") and item["cert"]!=payload.cert:
            raise HTTPException(422,"Certificate contradicts the listing evidence.")
        result.update(payload.model_dump(),status="verified",confidence="owner-reviewed",condition_confidence="owner-reviewed",condition_key=condition_key(item),reviewed_at=now())
        with db.connect() as c:
            # One physical listing cannot simultaneously verify two incompatible printings.
            other=c.execute("SELECT data FROM listing_matches WHERE listing_id=? AND variant_id!=?",(ident,v["id"])).fetchall()
            if any(json.loads(r[0]).get("status")=="verified" for r in other):
                raise HTTPException(409,"This listing is already verified against another variant.")
            c.execute("INSERT INTO listing_matches VALUES(?,?,?) ON CONFLICT(listing_id,variant_id) DO UPDATE SET data=excluded.data",(ident,v["id"],dumps(result)))
        evaluate_alerts(db); db.activity("Exact card and condition review saved")
        return result

    @app.post("/api/listings/{ident}/unavailable")
    def unavailable(ident:str):
        rows=db.rows("SELECT data FROM listings WHERE id=?",(ident,))
        if not rows:
            raise HTTPException(404,"Listing not found")
        item=json.loads(rows[0]["data"]); item.update(status="unavailable",checked_at=now(),unavailable_reason="Owner marked unavailable; not a completed-sale record")
        with db.connect() as c:
            c.execute("UPDATE listings SET data=?,checked_at=? WHERE id=?",(dumps(item),item["checked_at"],ident))
            snapshot_listing(c,item)
        return {"ok":True}

    def save_sale(payload,c):
        variant(payload.variant_id,True)
        item=payload.model_dump(mode="json"); item["id"]=uuid.uuid4().hex
        item["source_url"]=canonical_url(item["source_url"])
        # The same linked transaction cannot be imported under another source name or variant.
        # eBay item URLs already identify one transaction; arbitrary extra IDs cannot inflate it.
        ebay_single=urlsplit(item["source_url"]).hostname=="www.ebay.com"
        key=hashlib.sha256(dumps([item["source_url"],"single" if ebay_single else item["transaction_id"] or "single"]).encode()).hexdigest()
        item["transaction_key"]=key
        c.execute("INSERT INTO sales VALUES(?,?,?,?)",(item["id"],item["variant_id"],key,dumps(item)))
        return item

    @app.post("/api/sales")
    def sale(payload:SaleIn):
        with db.connect() as c:
            item=save_sale(payload,c)
        db.activity("Completed-sale evidence saved"); evaluate_alerts(db)
        return item

    @app.delete("/api/sales/{ident}")
    def delete_sale(ident:str):
        with db.connect() as c:
            c.execute("DELETE FROM sales WHERE id=?",(ident,))
        return {"ok":True}

    @app.post("/api/sources/ebay")
    async def credentials(payload:CredentialsIn):
        return await connect_ebay(db,config,payload.model_dump(),prefs())

    @app.delete("/api/sources/ebay")
    def disconnect():
        with db.connect() as c:
            c.execute("DELETE FROM kv WHERE key='ebay_credentials'")
        db.put("ebay_status",{"status":"missing_credentials","message":"Disconnected by owner","checked_at":now()})
        return {"ok":True}

    @app.post("/api/sources/fx")
    async def fx():
        return await refresh_fx(db)

    @app.put("/api/sources/pricecharting")
    def connect_pricecharting(payload:PriceChartingCredentials):
        aggregates.store_token(db,config,payload.token)
        return db.get('pricecharting_status')

    @app.delete("/api/sources/pricecharting")
    def disconnect_pricecharting():
        aggregates.disconnect(db)
        return {'ok':True}

    @app.post("/api/cards/{vid}/public-guides")
    async def public_guide(vid:str,payload:PublicGuideRequest):
        v=variant(vid,True)
        try: return await public_guides.refresh_guides(db,v,payload)
        except SourceError as ex:
            return JSONResponse({"detail":ex.message,"status":ex.status},422)

    @app.post("/api/sources/pricecharting/product")
    async def pricecharting_product(payload:AggregateRequest):
        variant(payload.variant_id,True)
        try: return await aggregates.refresh_product(db,config,payload)
        except SourceError as ex:
            return JSONResponse({'detail':ex.message,'status':ex.status},422)

    @app.get("/api/monitor")
    def monitor_status():
        return {"last_execution":db.get("monitor_heartbeat"),"scheduler_enabled":config.scheduler,
                "wake_interval_seconds":config.tick_seconds,"scheduler_state":db.get("scheduler_state"),"scheduler_last_result":db.get("scheduler_last_result"),"paused":prefs()["paused"],"refresh_hours":prefs()["refresh_hours"],
                "history":[json.loads(r["data"]) for r in db.rows("SELECT data FROM scan_log ORDER BY time DESC LIMIT 20")]}

    @app.post("/api/monitor")
    async def monitor(request:Request):
        try:
            raw=await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
        except (ValueError,TypeError):
            raise HTTPException(422,"Expected a JSON object") from None
        if not isinstance(raw,dict) or any(k!="force" for k in raw) or ("force" in raw and not isinstance(raw["force"],bool)):
            raise HTTPException(422,"Expected an object with an optional boolean force field")
        # A service caller cannot bypass the owner's saved interval.
        force=bool(raw.get("force",False)) and request.state.owner
        return await run_monitor(db,config,"manual" if request.state.owner else "service",force=force)

    @app.get("/api/alerts")
    def alerts():
        return {"alerts":[{**json.loads(r["data"]),"id":r["id"],"read":bool(r["read"]),"created_at":r["created_at"]} for r in db.rows("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 200")]}

    @app.post("/api/alerts/read")
    def read_alerts():
        with db.connect() as c:
            c.execute("UPDATE alerts SET read=1")
        return {"ok":True}

    @app.get("/api/export/{kind}")
    def export(kind:str):
        if kind not in IMPORT_MODELS:
            raise HTTPException(404,"Unknown export")
        model=IMPORT_MODELS[kind]; records=db.records(kind)
        if kind=="listings":
            records=[]
            for row in db.rows("SELECT l.data,m.variant_id FROM listings l JOIN listing_matches m ON m.listing_id=l.id"):
                records.append({**json.loads(row["data"]),"variant_id":row["variant_id"]})
        output=io.StringIO(newline=""); columns=list(model.model_fields)
        w=csv.DictWriter(output,fieldnames=columns,extrasaction="ignore"); w.writeheader()
        for row in records:
            sanitized={}
            for k in columns:
                value=row.get(k,"")
                if isinstance(value,(dict,list)):
                    value=dumps(value)
                if isinstance(value,bool):
                    value="true" if value else "false"
                # Apostrophe-prefixed CSV cells cannot execute spreadsheet formulas.
                if isinstance(value,str) and (value.startswith("'") or value.lstrip().startswith(("=","+","-","@","\t","\r"))):
                    value="'"+value
                sanitized[k]=value
            w.writerow(sanitized)
        return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="ember-{kind}.csv"'})

    @app.get("/api/import/template/{kind}")
    def template(kind:str):
        if kind not in IMPORT_MODELS:
            raise HTTPException(404,"Unknown template")
        return Response(",".join(IMPORT_MODELS[kind].model_fields)+"\n",media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="ember-{kind}-template.csv"'})

    @app.post("/api/import")
    def import_csv(payload:ImportIn):
        model=IMPORT_MODELS[payload.kind]; errors=[]; parsed=[]
        reader=csv.DictReader(io.StringIO(payload.csv_text.lstrip("\ufeff")))
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):
            raise HTTPException(422,"Missing or duplicate CSV headers")
        unknown=set(reader.fieldnames)-set(model.model_fields)
        if unknown:
            raise HTTPException(422,"Unknown CSV columns: "+", ".join(unknown))
        for index,row in enumerate(reader,start=2):
            if index>1001:
                raise HTTPException(413,"Import at most 1000 rows at a time")
            if None in row:
                errors.append({"row":index,"message":"More cells than CSV headers"})
                continue
            # Empty optional fields use model defaults. Explicit zeros remain zeros.
            row={k:v for k,v in row.items() if v not in {"",None}}
            if row.get("grader") in {"RAW","UNKNOWN"} and "grade" not in row:
                row['grade']=None
            try:
                for key in ['targets','fallback_buckets']:
                    if key in row: row[key]=json.loads(row[key])
            except (ValueError,TypeError):
                errors.append({'row':index,'message':'Targets/bucket fields must contain valid JSON.'})
                continue
            for k,value in list(row.items()):
                if isinstance(value,str) and value.startswith("''"):
                    row[k]=value[1:]
                elif isinstance(value,str) and value.startswith("'") and value[1:].lstrip().startswith(("=","+","-","@")):
                    row[k]=value[1:]
            try:
                item=model.model_validate(row)
                variant(item.variant_id,payload.kind in {"copies","sales"})
                parsed.append(item)
            except (ValidationError,HTTPException) as e:
                errors.append({"row":index,"message":str(e.detail) if isinstance(e,HTTPException) else "; ".join(x["msg"] for x in e.errors())})
        if errors:
            return {"ok":False,"rows":len(parsed),"errors":errors,"committed":False}
        # Validate uniqueness AND insert atomically. A preview uses a rolled-back transaction.
        handlers={"copies":save_copy,"sales":save_sale,"listings":save_manual_listing,"watchlist":save_watch}
        try:
            with db.connect() as c:
                c.execute("BEGIN IMMEDIATE")
                for item in parsed:
                    handlers[payload.kind](item,c)
                if not payload.commit:
                    c.rollback()
        except sqlite3.IntegrityError:
            return {"ok":False,"rows":len(parsed),"errors":[{"row":"batch","message":"Duplicate certification or transaction, including duplicates within this CSV. Nothing imported."}],"committed":False}
        if payload.commit:
            db.activity(f"Imported {len(parsed)} {payload.kind} rows"); evaluate_alerts(db)
        return {"ok":True,"rows":len(parsed),"errors":[],"committed":payload.commit}

    return app
