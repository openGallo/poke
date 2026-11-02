"""Source-backed catalogue. Discovery never infers a complete physical variant census."""
from datetime import date
import asyncio
import json
from urllib.parse import quote
import httpx
from .config import ROOT
from .db import dumps, now
from .models import Variant, LANGUAGES, norm
from .matching import NAMES

GAPS = [
    "This is a partial catalogue, not a verified worldwide census or PSA population report.",
    "Catalogue combines the preserved 2.1 identities with the original Ember source-linked snapshot. It is not a fresh source check or a claim that PSA 10 copies exist.",
    "First editions, print runs, foil patterns, retailer stamps, regional promos and jumbo printings may be missing.",
    "Provisional records establish a known card but not a sufficiently resolved collectible; they cannot accept ownership or recommendations.",
    "Artwork-only cameos are opt-in and not yet catalogued. Add documented records manually.",
    "PSA 10 availability is unknown until an eligible listing or authentic owned slab is recorded.",
    "Some artwork links may be unavailable. Reference art is not evidence of an exact stamp, finish, or actual slab.",
]


def in_scope(v, p):
    return not v.get("retired") and v["language"] in p["languages"] and (not p["release_types"] or v["release_type"] in p["release_types"]) and (not p["finishes"] or v["finish"] in p["finishes"]) and (not p.get("editions") or v["edition"] in p["editions"]) and (not p.get("stamps") or v["stamp"] in p["stamps"]) and (not p.get("sizes") or v["size"] in p["sizes"]) and (not v["artwork_only"] or p["artwork_only"]) and (not v["announced"] or p["include_announced"])


def store_variant(db, v):
    item = Variant.model_validate(v).model_dump()
    with db.connect() as c:
        existing = c.execute("SELECT data FROM variants WHERE id=?", (item["id"],)).fetchone()
        # Provider updates must never downgrade or overwrite a user-resolved record.
        if existing:
            old = json.loads(existing[0])
            if old["identity_status"] == "documented" or old.get("retired"):
                return old
        c.execute("INSERT INTO variants VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (item["id"],item["base_id"],dumps(item)))
    return item


def seed(db):
    data = json.loads((ROOT/"data"/"catalogue.json").read_text())
    version=data.get("version", "2.0")
    if db.get("seed_version") == version:
        return
    variants=[Variant.model_validate(v).model_dump() for v in data["variants"]]
    superseded=set(data.get("superseded_provisional_ids", []))
    metadata={k:v for k,v in data.items() if k not in {"variants", "legacy_aliases", "superseded_provisional_ids"}}
    # One atomic transaction makes startup fast and prevents a half-applied catalogue.
    with db.connect() as c:
        c.execute("BEGIN IMMEDIATE")
        existing={row["id"]:json.loads(row["data"]) for row in c.execute("SELECT id,data FROM variants")}
        used={row[0] for row in c.execute("SELECT variant_id FROM copies UNION SELECT variant_id FROM watchlist UNION SELECT variant_id FROM sales UNION SELECT variant_id FROM listing_matches")}
        for v in variants:
            old=existing.get(v["id"])
            if old and (old["identity_status"]=="documented" or old.get("retired") or v["id"] in superseded):
                continue
            c.execute("INSERT INTO variants VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",(v["id"],v["base_id"],dumps(v)))
        for ident in superseded-used:
            old=existing.get(ident)
            if old and old["identity_status"]=="provisional":
                old["retired"]=True
                c.execute("UPDATE variants SET data=? WHERE id=?",(dumps(old),ident))
        for key,value in [("seed_version",version),("seed_metadata",metadata)]:
            c.execute("INSERT INTO kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,dumps(value)))


def from_tcgdex(card, lang, set_info):
    if card.get("category", "Pokemon").lower() != "pokemon":
        return []
    dex = card.get("dexId", [])
    if 4 not in dex and not any(n in norm(card.get("name", "")) for n in NAMES.get(lang, [])):
        return []
    set_id = card.get("set", {}).get("id", "")
    # Pocket has distinct series; reject positively, not based on art alone.
    series_id = set_info.get("serie", {}).get("id", "")
    if series_id in {"tcgp", "pocket"} or set_info.get("tcgOnline") == "pocket":
        return []
    if not set_id:
        return []
    release = set_info.get("releaseDate", "")
    number = str(card.get("localId", ""))
    total = card.get("set", {}).get("cardCount", {}).get("official")
    if total:
        number += "/" + str(total)
    source = f"https://api.tcgdex.net/v2/{quote(lang)}/cards/{quote(card['id'])}"
    base = {"base_id": f"{lang}:{set_id}:{card.get('localId')}", "provider_id": card["id"], "language": lang,
            "name": card["name"], "set_name": card["set"].get("name", set_id), "set_code": set_id,
            "number": number, "year": int(release[:4]) if len(release)>=4 and release[:4].isdigit() else None,
            "announced": release[:10] > date.today().isoformat() if release else False,
            "source_url": source, "source_checked_at": now(),
            "image_url": card.get("image", "") + "/high.webp" if card.get("image") else "",
            "release_type": "Promo" if "promo" in norm(card["set"].get("name", "")) else "Expansion"}
    # Existing local research for this base wins. API flags often do not disambiguate stamps/editions.
    raw = card.get("variants", {})
    items = []
    if isinstance(raw, list):
        for r in raw:
            item = {**base, "finish": r.get("type", "unspecified"), "edition": r.get("subtype", "unspecified"),
                    "stamp": ", ".join(r.get("stamp", [])) or "none", "size": r.get("size", "standard"),
                    "print_run": " / ".join(str(x) for x in [r.get("subtype","standard"),r.get("foil")] if x), "identity_status": "provisional",
                    "notes": "Provider-specified variant; verify language-specific edition, foil and stamp before documenting."}
            items.append(Variant.model_validate(item).model_dump())
    else:
        for field, finish in [("normal", "normal"), ("holo", "holo"), ("reverse", "reverse-holo")]:
            if raw.get(field):
                items.append(Variant.model_validate({**base, "finish": finish,
                    "notes": "Provider finish flag; edition, stamps and regional print runs still require review."}).model_dump())
    if not items:
        items = [Variant.model_validate({**base, "notes": "Printing details are not supplied by the source."}).model_dump()]
    return items


async def sync_language(db, language, client=None):
    if language not in LANGUAGES:
        raise ValueError("Unsupported language")
    lease = db.lease("catalogue", 1800)
    if not lease:
        return {"status": "busy", "message": "A catalogue synchronization is already running."}
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=12, follow_redirects=False)
    result = {"language": language, "checked_at": now(), "status": "partial", "processed": 0, "added": 0, "errors": []}
    try:
        name = NAMES[language][0]
        r = await client.get(f"https://api.tcgdex.net/v2/{language}/cards", params={"name": name})
        r.raise_for_status()
        cards = r.json()
        if not isinstance(cards, list):
            raise ValueError("Unexpected provider response")
        cards = sorted(cards, key=lambda c: c["id"])
        cursor = db.get("catalogue_cursor:"+language, 0)
        if cursor >= len(cards):
            cursor = 0
        batch = cards[cursor:cursor+30]
        sets = {}
        for brief in batch:
            try:
                r = await client.get(f"https://api.tcgdex.net/v2/{language}/cards/{quote(brief['id'])}")
                r.raise_for_status()
                card = r.json(); sid = card.get("set", {}).get("id")
                if sid not in sets:
                    sr = await client.get(f"https://api.tcgdex.net/v2/{language}/sets/{quote(sid or '')}")
                    sr.raise_for_status(); sets[sid] = sr.json()
                new = from_tcgdex(card, language, sets[sid])
                for v in new:
                    # Avoid creating unresolved duplicates of an already documented base.
                    existing = db.rows("SELECT data FROM variants WHERE base_id=?", (v["base_id"],))
                    if any(json.loads(x["data"])["identity_status"] == "documented" for x in existing):
                        # Keep provider variant discoveries for review without duplicating binder completion.
                        findings=db.get("catalogue_discovery:"+v["base_id"],[])
                        if v["id"] not in {x["id"] for x in findings}:
                            db.put("catalogue_discovery:"+v["base_id"],findings+[v])
                        continue
                    present = bool(db.rows("SELECT id FROM variants WHERE id=?", (v["id"],)))
                    store_variant(db, v)
                    result["added"] += int(not present)
                result["processed"] += 1
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                result["errors"].append(f"Could not import card {brief.get('id', 'unknown')}; retry on the next pass.")
            await asyncio.sleep(0.05)
        end = cursor + len(batch)
        db.put("catalogue_cursor:"+language, end if end < len(cards) else 0)
        result.update({"found_by_provider": len(cards), "batch_start": cursor, "batch_end": end,
                       "status": "provider_pass_complete" if end >= len(cards) and not result["errors"] else "partial"})
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        result.update(status="connection_error", errors=["TCGdex was not reachable or returned an unsupported response. Existing catalogue preserved."])
    finally:
        if own_client:
            await client.aclose()
        db.release("catalogue", lease)
    db.put("catalogue_sync:"+language, result)
    return result
