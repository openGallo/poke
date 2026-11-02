"""Offline contract tests for source APIs; these fixtures are not real market data."""
import asyncio
import json
import pytest
import httpx
from ember import aggregates
from ember.db import dumps
from ember.models import AggregateRequest,Preferences
from ember.providers import SourceError, normalize_ebay, save_listing
from ember.conditions import condition_key
from ember.security import encrypt
from ember.monitor import run_monitor

TOKEN='synthetic-price-guide-token-not-a-real-secret'

def aggregate_run(db,config,card,handler,confirmed=True,product='12345'):
 async def go():
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
   return await aggregates.refresh_product(db,config,AggregateRequest(variant_id=card['id'],product_id=product,product_identity_confirmed=confirmed),c)
 return asyncio.run(go())


def test_aggregate_is_not_a_sale_and_token_never_leaks(owner,app,config,card):
 db=app.state.db
 assert owner.put('/api/sources/pricecharting',json={'token':TOKEN}).status_code==200
 assert TOKEN not in str(db.get('pricecharting_token'))
 assert TOKEN not in owner.get('/api/state').text
 calls=[]
 def handler(req):
  calls.append(req)
  assert req.method=='GET' and req.url.params['t']==TOKEN
  return httpx.Response(200,json={'status':'success','id':'12345','product-name':'SYNTHETIC Charmander','console-name':'SYNTHETIC TEST ONLY','manual-only-price':10000,'loose-price':2000,'graded-price':5000,'unexpected-secret':TOKEN})
 result=aggregate_run(db,config,card,handler)
 assert not result['cached'] and len(result['observations'])==3 and len(calls)==1
 assert db.records('sales')==[] and db.records('listings')==[]
 stored=str(db.rows('SELECT data FROM aggregates'))
 assert TOKEN not in stored and 'aggregate_estimate' in stored
 d=owner.get('/api/cards/'+card['id']).json()
 assert d['market']['count']==0 and d['market']['reference'] is None
 assert len(d['aggregate_observations'])==3
 again=aggregate_run(db,config,card,handler)
 assert again['cached'] and len(calls)==1 and len(db.rows('SELECT data FROM aggregates'))==3
 assert owner.delete('/api/sources/pricecharting').status_code==200
 assert not db.rows('SELECT data FROM aggregates') and db.get('pricecharting_token') is None
 assert not db.rows("SELECT * FROM kv WHERE key LIKE 'pricecharting_cache:%'")

@pytest.mark.parametrize('body',[[],{'status':'error','error-message':TOKEN},{'status':'success','id':'different'}])
def test_bad_provider_payload_explicit_sanitized(app,config,card,body):
 aggregates.store_token(app.state.db,config,TOKEN)
 with pytest.raises(SourceError) as ex:
  aggregate_run(app.state.db,config,card,lambda _:httpx.Response(200,json=body))
 assert TOKEN not in ex.value.message
 assert not app.state.db.rows('SELECT * FROM aggregates')
 assert app.state.db.get('pricecharting_status')['status']=='provider_error'


def test_unconfirmed_product_missing_credentials_and_rate_limit(app,config,card):
 calls=[]
 def handler(req):calls.append(req);return httpx.Response(500)
 with pytest.raises(SourceError,match='Confirm the exact'): aggregate_run(app.state.db,config,card,handler,False)
 with pytest.raises(SourceError,match='existing licensed'): aggregate_run(app.state.db,config,card,handler)
 aggregates.store_token(app.state.db,config,TOKEN)
 def good(req):calls.append(req);return httpx.Response(200,json={'status':'success','id':'12345','loose-price':1000})
 aggregate_run(app.state.db,config,card,good)
 with pytest.raises(SourceError,match='two seconds'): aggregate_run(app.state.db,config,card,good,product='12346')
 assert len(calls)==1


def item(**changes):
 return {'itemId':'v1|123456789012|0','itemWebUrl':'https://www.ebay.com/itm/123456789012','title':'Charmander 46/102 Base Set Unlimited English raw','buyingOptions':['FIXED_PRICE'],'price':{'value':'20','currency':'EUR'},'condition':'Used','shippingOptions':[{'shippingCost':{'value':'10','currency':'EUR'}},{'shippingCost':{'value':'5','currency':'EUR'}}]}|changes


def test_ebay_used_unknown_original_and_cheapest_shipping():
 data=normalize_ebay(item(),Preferences().model_dump())
 assert data['grader']=='RAW' and data['raw_condition']=='Unknown' and data['condition_original']=='Used'
 assert data['shipping']==5 and data['import_cost'] is None and data['fees'] is None


def test_ebay_raw_precise_condition_and_multiple_graders():
 p=Preferences().model_dump()
 raw=normalize_ebay(item(condition='Near Mint or Better'),p)
 assert condition_key(raw)=='raw:ebay:Near Mint or Better'
 cgc=normalize_ebay(item(title='Charmander 46/102 English CGC Pristine 10',condition='Graded'),p)
 assert cgc['grader']=='CGC' and cgc['grading_scale']=='unspecified'


def test_monitor_alternative_owned_still_searches_psa_and_raw(owner,app,config,card,copy_payload):
 db=app.state.db;p=Preferences().model_dump()|{'paused':False,'monitor_mode':'watchlist'};db.put('preferences',p)
 owner.post('/api/copies',json=copy_payload|{'grader':'RAW','grade':None,'raw_condition':'Near Mint','cert':'','psa10_confirmed':False,'condition_confirmed':True})
 owner.put('/api/watchlist',json={'variant_id':card['id']})
 db.put('ebay_credentials',encrypt(config,dumps({'client_id':'synthetic','client_secret':'test-source-secret'})))
 queries=[]
 def handler(req):
  if 'oauth2' in req.url.path:return httpx.Response(200,json={'access_token':'test-only-access','expires_in':3600})
  if 'item_summary/search' in req.url.path:
   queries.append(req.url.params['q']);return httpx.Response(200,json={'total':0,'itemSummaries':[]})
  raise AssertionError('Unexpected read request')
 async def go():
  async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:return await run_monitor(db,config,client=c,requested_variant=card['id'])
 result=asyncio.run(go())
 assert len(queries)==2 and sum('PSA 10' in q for q in queries)==1
 assert result['scanned_variants']==1 and result['status']=='completed'
 coverage=db.get('scan_coverage:'+card['id']);assert coverage['includes_fallbacks'] is True
 detail=owner.get('/api/cards/'+card['id']).json()
 assert 'No PSA 10 listing found' in detail['psa10_summary']


def test_failed_source_never_claims_complete_coverage(owner,app,config,card):
 db=app.state.db;db.put('preferences',Preferences().model_dump()|{'paused':False})
 r=owner.post('/api/cards/'+card['id']+'/scan').json()
 assert r['status']=='missing_credentials' and r['scanned_variants']==0
 d=owner.get('/api/cards/'+card['id']).json()
 assert not d['scan_current'] and 'could not be checked' in d['psa10_summary']
 sources=owner.get('/api/sources').json()
 assert 'missing_credentials' in str(sources) and 'manual' in str(sources)
