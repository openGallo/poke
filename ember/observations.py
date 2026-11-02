"""Real observation snapshots only: asking prices are never recorded as completed sales."""
import hashlib
import json
from .conditions import condition_key, condition_label
from .db import dumps


def snapshot_listing(conn,listing):
    fields={k:listing.get(k) for k in ["price","currency","shipping","fees","import_cost","destination_country","listing_type","status","title","url","source","seller","seller_country","delivery_eligible"]}
    fields.update(condition_key=condition_key(listing),condition_label=condition_label(listing),
                  observation_type="auction_bid" if listing.get("listing_type")=="auction" else "asking_price")
    fp=hashlib.sha256(dumps(fields).encode()).hexdigest()
    last=conn.execute("SELECT fingerprint FROM listing_history WHERE listing_id=? ORDER BY id DESC LIMIT 1",(listing['id'],)).fetchone()
    if last and last[0]==fp: return
    conn.execute("INSERT OR IGNORE INTO listing_history(listing_id,fingerprint,observed_at,data) VALUES(?,?,?,?)",
                 (listing['id'],fp,listing['checked_at'],dumps(fields)))


def history_for(db,vid):
    rows=db.rows("SELECT h.observed_at,h.data,h.listing_id FROM listing_history h JOIN listing_matches m ON m.listing_id=h.listing_id WHERE m.variant_id=? ORDER BY h.observed_at DESC LIMIT 500",(vid,))
    return [{**json.loads(r['data']),'observed_at':r['observed_at'],'listing_id':r['listing_id']} for r in rows]
