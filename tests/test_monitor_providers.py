"""Official API transport contracts exercised only with synthetic HTTP fixtures."""
import asyncio
from dataclasses import replace
from datetime import date
import json
import time
import httpx
from ember.db import now,dumps
from ember.models import Preferences
from ember.security import encrypt
from ember.monitor import run_monitor,evaluate_alerts,scheduler_loop
from ember.providers import normalize_ebay,save_listing,refresh_fx,connect_ebay
from ember.catalogue import sync_language


def unpause(db,**kw):
    p=Preferences().model_dump()|{'paused':False}|kw
    db.put('preferences',p);return p


def credentials(db,config):
    db.put('ebay_credentials',encrypt(config,dumps({'client_id':'test-client-id','client_secret':'synthetic-secret-not-production'})))


def ebay_item(**kw):
    return {'itemId':'v1|123456789012|0','itemWebUrl':'https://www.ebay.com/itm/123456789012','title':'Charmander 46/102 Base Set Unlimited English PSA 10','buyingOptions':['FIXED_PRICE'],'price':{'value':'75','currency':'EUR'},'shippingOptions':[{'shippingCost':{'value':'5','currency':'EUR'}}],'seller':{'username':'SYNTHETIC_TEST_SELLER'}}|kw


def test_missing_credentials_explicit(app,config):
    unpause(app.state.db)
    r=asyncio.run(run_monitor(app.state.db,config))
    assert r['status']=='missing_credentials' and r['scanned_variants']==0
    assert app.state.db.get('monitor_heartbeat')['checkedAt']==r['checkedAt']


def test_pause_and_interval_send_no_requests(app,config):
    count=[]
    def handler(req):count.append(req);return httpx.Response(500)
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            r=await run_monitor(app.state.db,config,force=True,client=c)
            assert r['status']=='paused'
            unpause(app.state.db);app.state.db.put('last_scan_attempt',now())
            r=await run_monitor(app.state.db,config,client=c)
            assert r['status']=='not_due'
    asyncio.run(go());assert count==[]


def test_lease_prevents_overlapping_runs(app,config):
    token=app.state.db.lease('monitor')
    r=asyncio.run(run_monitor(app.state.db,config))
    assert r['status']=='busy' and app.state.db.get('monitor_heartbeat') is None
    app.state.db.release('monitor',token)


def test_actual_scheduler_loop_persists_timed_execution(app,config):
    async def go():
        task=asyncio.create_task(scheduler_loop(app.state.db,replace(config,tick_seconds=.025)))
        for _ in range(100):
            await asyncio.sleep(.01)
            if app.state.db.get('monitor_heartbeat'):break
        task.cancel()
        try:await task
        except asyncio.CancelledError:pass
    asyncio.run(go())
    r=app.state.db.get('monitor_heartbeat')
    assert r['trigger']=='scheduled' and r['status']=='paused' and r['checkedAt']


def test_official_api_flow_watchlist_scope_and_direct_disappearance(app,config,card):
    db=app.state.db;unpause(db,languages=['en'],monitor_mode='watchlist');credentials(db,config)
    with db.connect() as c:c.execute('INSERT INTO watchlist VALUES(?,?)',(card['id'],dumps({'variant_id':card['id'],'priority':5,'target_price':None,'currency':'EUR'})))
    calls=[]
    def handler(req):
        calls.append(str(req.url))
        if '/oauth2/token' in str(req.url):return httpx.Response(200,json={'access_token':'synthetic-access-token','expires_in':3600})
        if '/item_summary/search' in str(req.url):return httpx.Response(200,json={'total':1,'itemSummaries':[ebay_item()]})
        return httpx.Response(404)
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await run_monitor(db,config,client=c)
    r=asyncio.run(go())
    assert r['status']=='completed' and r['scanned_variants']==1 and r['rechecked_listings']==1
    assert len(calls)==4 and db.records('listings')[0]['status']=='unavailable'
    assert db.records('sales')==[]


def test_search_omission_does_not_imply_sold(app,config,card):
    db=app.state.db;p=unpause(db,languages=['en']);credentials(db,config)
    save_listing(db,normalize_ebay(ebay_item(),p),card)
    def handler(req):
        if '/oauth2/token' in str(req.url):return httpx.Response(200,json={'access_token':'test','expires_in':3600})
        if '/item_summary/search' in str(req.url):return httpx.Response(200,json={'total':0,'itemSummaries':[]})
        return httpx.Response(200,json=ebay_item())
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await run_monitor(db,config,client=c)
    r=asyncio.run(go())
    assert r['status']=='partial' and db.records('listings')[0]['status']=='active'
    assert not db.records('sales')


def test_auction_current_bid_and_unknown_imports():
    p=Preferences().model_dump()
    item=ebay_item(buyingOptions=['AUCTION','FIXED_PRICE'],price={'value':'900','currency':'EUR'},currentBidPrice={'value':'10','currency':'EUR'})
    l=normalize_ebay(item,p)
    assert l['listing_type']=='auction' and l['price']==10 and l['import_cost'] is None
    assert normalize_ebay(ebay_item(price={'value':'NaN','currency':'EUR'}),p) is None


def test_updated_identity_invalidates_other_matches(owner,app,card,listing_payload,review_payload):
    l=owner.post('/api/listings',json=listing_payload).json()
    owner.post('/api/listings/'+l['id']+'/review',json=review_payload)
    other=next(v for v in app.state.db.records('variants') if v['id']!=card['id'] and v['identity_status']=='documented')
    p=Preferences().model_dump()
    fresh=normalize_ebay(ebay_item(title='Charmander 46/102 English PSA 9'),p)
    save_listing(app.state.db,fresh,other)
    match=json.loads(app.state.db.rows('SELECT data FROM listing_matches WHERE listing_id=? AND variant_id=?',(l['id'],card['id']))[0]['data'])
    assert match['status']!='verified'


def test_alert_dedup_budget_scope_and_pause(owner,app,card,listing_payload,review_payload):
    db=app.state.db;unpause(db,budget=100)
    l=owner.post('/api/listings',json=listing_payload).json()
    assert owner.put('/api/watchlist',json={'variant_id':card['id'],'target_price':80}).status_code==200
    owner.post('/api/listings/'+l['id']+'/review',json=review_payload)
    assert len(owner.get('/api/alerts').json()['alerts'])==1
    assert evaluate_alerts(db)==0
    owner.post('/api/listings',json=listing_payload|{'price':60})
    unpause(db,budget=50)
    owner.post('/api/listings/'+l['id']+'/review',json=review_payload)
    assert len(owner.get('/api/alerts').json()['alerts'])==1
    unpause(db,budget=100,languages=['ja'])
    assert evaluate_alerts(db)==0
    unpause(db,budget=100)
    assert evaluate_alerts(db)==1
    assert evaluate_alerts(db)==0
    prefs=db.get('preferences');prefs['paused']=True;db.put('preferences',prefs)
    assert evaluate_alerts(db)==0


def test_credentials_only_saved_after_browse_test(app,config):
    db=app.state.db
    def handler(req):
        if '/oauth2/' in str(req.url):return httpx.Response(200,json={'access_token':'synthetic','expires_in':3600})
        return httpx.Response(403)
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await connect_ebay(db,config,{'client_id':'testclient','client_secret':'testsecret'},Preferences().model_dump(),client=c)
    r=asyncio.run(go())
    assert r['status']=='access_error' and db.get('ebay_credentials') is None


def test_fx_missing_connection_never_creates_rates(app):
    def handler(req):raise httpx.ConnectError('synthetic transport outage')
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await refresh_fx(app.state.db,c)
    r=asyncio.run(go())
    assert r['status']=='connection_error' and app.state.db.get('fx') is None


def test_fx_rejects_nonfinite_provider_values(app):
    def handler(req):return httpx.Response(200,content=b'{"date":"2026-10-10","rates":{"USD":NaN}}')
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await refresh_fx(app.state.db,c)
    assert asyncio.run(go())['status']=='connection_error'


def test_catalogue_sync_connection_failure_preserves_seed(app):
    before=app.state.db.records('variants')
    def handler(req):raise httpx.ConnectError('synthetic outage')
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await sync_language(app.state.db,'en',c)
    r=asyncio.run(go())
    assert r['status']=='connection_error' and app.state.db.records('variants')==before


def test_monitor_does_not_recheck_outside_watchlist(app,config,card):
    db=app.state.db;p=unpause(db,monitor_mode='watchlist');credentials(db,config)
    save_listing(db,normalize_ebay(ebay_item(),p),card)
    calls=[]
    def handler(req):calls.append(req);return httpx.Response(500)
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await run_monitor(db,config,client=c)
    r=asyncio.run(go())
    assert r['status']=='no_eligible_cards' and calls==[]


def test_manual_cost_edit_retains_ebay_monitoring_link(owner,app,card,listing_payload):
    db=app.state.db
    save_listing(db,normalize_ebay(ebay_item(),Preferences().model_dump()),card)
    assert owner.post('/api/listings',json=listing_payload).status_code==200
    assert db.records('listings')[0]['provider_id']=='v1|123456789012|0'


def test_provider_price_change_invalidates_manual_import_estimate(app,card):
    p=Preferences().model_dump();old=normalize_ebay(ebay_item(),p)
    old.update(fees=2,import_cost=15)
    save_listing(app.state.db,old,card)
    new=normalize_ebay(ebay_item(price={'value':'50','currency':'EUR'}),p)
    save_listing(app.state.db,new,card)
    row=app.state.db.records('listings')[0]
    assert row['fees'] is None and row['import_cost'] is None


def test_cross_marketplace_same_slab_deduplicates_alerts(owner,app,card,listing_payload,review_payload):
    db=app.state.db;unpause(db,budget=100)
    owner.put('/api/watchlist',json={'variant_id':card['id'],'target_price':80})
    first=owner.post('/api/listings',json=listing_payload).json()
    assert owner.post('/api/listings/'+first['id']+'/review',json=review_payload).status_code==200
    second=owner.post('/api/listings',json=listing_payload|{'url':'https://example.com/slabs/synthetic-duplicate'}).json()
    assert owner.post('/api/listings/'+second['id']+'/review',json=review_payload).status_code==200
    assert len(db.rows('SELECT id FROM alerts'))==1
    assert evaluate_alerts(db)==0
