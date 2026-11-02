"""Licensed current price guides. Never imported into the completed-sales table."""
import json
import hashlib
import time
import math
import httpx
from .db import dumps, now
from .security import encrypt, decrypt
from .providers import SourceError

PRICE_FIELDS={
 'loose-price':'Ungraded · condition unspecified',
 'manual-only-price':'PSA 10',
 'graded-price':'Grade 9 · grading company unspecified',
 'box-only-price':'Grade 9.5 · grading company unspecified',
 'new-price':'Grade 8 / 8.5 · grading company unspecified',
 'bgs-10-price':'BGS 10 · verify designation',
 'condition-17-price':'CGC 10 · scale era unspecified',
 'condition-19-price':'CGC Pristine 10 · scale era unspecified',
 'condition-20-price':'BGS Black Label 10',
}


async def product_request(db,token,product_id,client):
    last=db.get('pricecharting_last_request',0)
    if time.time()-last<2:
        raise SourceError('rate_limited','Wait at least two seconds between PriceCharting requests.')
    db.put('pricecharting_last_request',time.time())
    try:
        r=await client.get('https://www.pricecharting.com/api/product',params={'t':token,'id':product_id})
        if r.status_code!=200:
            raise SourceError('access_error',f'PriceCharting returned HTTP {r.status_code}. Check your existing API entitlement.')
        body=r.json()
        if not isinstance(body,dict) or body.get('status')!='success' or str(body.get('id'))!=product_id:
            raise SourceError('provider_error','PriceCharting did not return the requested product. No data saved.')
        return body
    except (httpx.HTTPError,ValueError,TypeError):
        # Never reflect the token-bearing request URL or provider error body.
        raise SourceError('connection_error','PriceCharting request failed. No completed sales or values were invented.') from None


def store_token(db,config,token):
    db.put('pricecharting_token',encrypt(config,token))
    db.put('pricecharting_status',{'status':'configured_unverified','checked_at':now(),'message':'Token stored encrypted. Run an explicit product refresh to test access; no subscription was purchased.'})


async def refresh_product(db,config,payload,client=None):
    if not payload.product_identity_confirmed:
        raise SourceError('identity_unconfirmed','Confirm the exact PriceCharting product including language and printing before linking it.')
    value=db.get('pricecharting_token')
    if not value: raise SourceError('missing_credentials','Configure your existing licensed PriceCharting API token.')
    own=client is None; client=client or httpx.AsyncClient(timeout=12,follow_redirects=False)
    lease=db.lease('pricecharting',60)
    if not lease:
        if own: await client.aclose()
        raise SourceError('busy','A PriceCharting refresh is already running.')
    try:
        cached=db.get('pricecharting_cache:'+payload.product_id)
        if cached and time.time()-cached['fetched_epoch']<86400:
            body=cached['body']; observed=cached['observed_at']
        else:
            try: token=decrypt(config,value)
            except Exception: raise SourceError('credential_error','Cannot decrypt the stored token; reconnect using this deployment configuration.') from None
            body=await product_request(db,token,payload.product_id,client)
            observed=now()
            # Cache only allowlisted public product fields, never token-bearing URLs/payloads.
            body={k:v for k,v in body.items() if k in {'id','product-name','console-name'}|set(PRICE_FIELDS)}
            db.put('pricecharting_cache:'+payload.product_id,{'body':body,'observed_at':observed,'fetched_epoch':time.time()})
        observations=[]
        for field,label in PRICE_FIELDS.items():
            try: amount=float(body.get(field))/100
            except (ValueError,TypeError): continue
            if not math.isfinite(amount) or not 0<amount<=100_000_000: continue
            item={'variant_id':payload.variant_id,'source':'PriceCharting','source_url':'https://www.pricecharting.com/game/'+payload.product_id,
                  'product_id':payload.product_id,'product_name':str(body.get('product-name',''))[:300],'product_group':str(body.get('console-name',''))[:300],
                  'source_field':field,'condition_label':label,'amount':amount,'currency':'USD','observed_at':observed,
                  'observation_type':'aggregate_estimate','sample_count':None,'sale_dates':None,
                  'identity_confidence':'owner-linked, not independently verified','notes':'Current aggregate estimate, not a known transaction or raw-condition-specific valuation. Excluded from deal recommendations.'}
            ident=hashlib.sha256(dumps([payload.variant_id,payload.product_id,field,observed]).encode()).hexdigest()
            with db.connect() as c: c.execute('INSERT OR IGNORE INTO aggregates VALUES(?,?,?)',(ident,payload.variant_id,dumps(item)))
            observations.append(item)
        db.put('pricecharting_status',{'status':'connected','checked_at':now(),'message':'Read-only current product estimates retrieved; not a historical sales feed.'})
        return {'observations':observations,'cached':bool(cached and observed==cached.get('observed_at'))}
    except SourceError as ex:
        db.put('pricecharting_status',{'status':ex.status,'checked_at':now(),'message':ex.message})
        raise
    finally:
        db.release('pricecharting',lease)
        if own: await client.aclose()


def disconnect(db):
    # The provider requires cached API values be purged when access ends.
    with db.connect() as c:
        c.execute("DELETE FROM kv WHERE key='pricecharting_token' OR key LIKE 'pricecharting_cache:%'")
        c.execute("DELETE FROM aggregates WHERE json_extract(data,'$.source')='PriceCharting'")
    db.put('pricecharting_status',{'status':'missing_credentials','checked_at':now(),'message':'Disconnected; cached provider estimates were removed.'})
