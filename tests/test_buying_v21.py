"""Synthetic data, ephemeral databases: dual completion and buying workflows."""
import asyncio
import csv
import io
import json
import sqlite3
from datetime import date
from fastapi.testclient import TestClient
from ember.conditions import condition_key, PSA10
from ember.db import DB, dumps, now
from ember.main import create_app
from ember.monitor import evaluate_alerts
from ember.models import Preferences
from conftest import TEST_PASSWORD

RAW={'grader':'RAW','grade':None,'raw_condition':'Near Mint','condition_scale':'seller','condition_original':'Near Mint'}
RAWKEY=condition_key(RAW)


def raw_copy(copy_payload):
 return copy_payload|RAW|{'cert':'','psa10_confirmed':False,'condition_confirmed':True}


def raw_listing(listing_payload,**kw):
 return listing_payload|RAW|{'title':'Charmander 46/102 Base Set Unlimited English raw Near Mint','cert':''}|kw


def raw_review(card):
 return {'variant_id':card['id'],'identity_confirmed':True,'photo_checked':True,'condition_checked':True,'notes':'Synthetic test photo and source checks, never actual evidence.'}


def add_raw(owner,card,listing_payload,**kw):
 r=owner.post('/api/listings',json=raw_listing(listing_payload,**kw)); assert r.status_code==200,r.text
 item=r.json()
 r=owner.post('/api/listings/'+item['id']+'/review',json=raw_review(card));assert r.status_code==200,r.text
 return item


def unpause(owner,**kw):
 p=owner.get('/api/state').json()['preferences']|{'paused':False}|kw
 r=owner.put('/api/settings',json=p); assert r.status_code==200,r.text


def test_dual_completion_multiple_copies_and_real_restart(owner,config,card,copy_payload):
 for _ in range(2): assert owner.post('/api/copies',json=raw_copy(copy_payload)).status_code==200
 state=owner.get('/api/state').json()
 assert state['completion']['owned']==0 and state['completion']['any_owned']==1 and state['completion']['upgrade_needed']==1
 record=next(v for v in state['variants'] if v['id']==card['id'])
 assert record['status']=='Alternative' and record['copies_count']==2
 # A second app and DB instance—not merely a browser refresh—reads existing records.
 with TestClient(create_app(config)) as restarted:
  login=restarted.post('/api/login',json={'password':TEST_PASSWORD});assert login.status_code==200
  assert restarted.get('/api/state').json()['completion']['any_owned']==1
 r=owner.post('/api/copies',json=copy_payload);assert r.status_code==200,r.text
 s=owner.get('/api/state').json()
 assert s['completion']['owned']==1 and s['completion']['any_owned']==1 and s['completion']['upgrade_needed']==0


def test_fallback_scope_changes_do_not_delete_ownership(owner,card,copy_payload):
 assert owner.post('/api/copies',json=raw_copy(copy_payload)).status_code==200
 unpause(owner,fallback_enabled=False)
 s=owner.get('/api/state').json()
 assert s['completion']['any_owned']==0 and s['completion']['upgrade_needed']==1 and len(s['copies'])==1
 assert owner.put('/api/watchlist',json={'variant_id':card['id'],'fallback_enabled':True,'fallback_buckets':[RAWKEY]}).status_code==200
 assert owner.get('/api/state').json()['completion']['any_owned']==1


def test_certificates_unique_per_grading_company(owner,app,copy_payload):
 assert owner.post('/api/copies',json=copy_payload).status_code==200
 bgs=copy_payload|{'grader':'BGS','grade':9.5,'psa10_confirmed':False,'condition_confirmed':True}
 assert owner.post('/api/copies',json=bgs).status_code==200
 assert owner.post('/api/copies',json=bgs).status_code==409
 assert {r['cert'] for r in app.state.db.rows('SELECT cert FROM copies')}=={'PSA:90000001','BGS:90000001'}


def test_migration_preserves_original_v2_json_and_image(tmp_path,card,copy_payload):
 path=tmp_path/'old.sqlite3'
 from ember.config import ROOT
 original={'id':'old-copy',**copy_payload,'photo_key':'old-photo'}
 with sqlite3.connect(path) as c:
  c.executescript((ROOT/'migrations/001_initial.sql').read_text())
  c.execute('INSERT INTO schema_migrations VALUES(?,?)',('001_initial.sql',now()))
  c.execute('INSERT INTO variants VALUES(?,?,?)',(card['id'],card['base_id'],dumps(card)))
  c.execute('INSERT INTO copies VALUES(?,?,?,?,?)',('old-copy',card['id'],'90000001',dumps(original),now()))
  c.execute('INSERT INTO images VALUES(?,?,?)',('old-photo',b'SYNTHETIC PRIVATE PHOTO','image/png'))
 db=DB(path)
 assert db.records('copies')==[original]
 assert db.rows('SELECT cert FROM copies')[0]['cert']=='PSA:90000001'
 assert db.rows('SELECT content FROM images')[0]['content']==b'SYNTHETIC PRIVATE PHOTO'
 DB(path); assert db.records('copies')==[original] # idempotent restart
 assert db.rows('SELECT * FROM listing_history')==[] # no manufactured old observations


def test_raw_review_does_not_require_or_accept_certificate(owner,card,listing_payload):
 l=owner.post('/api/listings',json=raw_listing(listing_payload)).json()
 assert owner.post('/api/listings/'+l['id']+'/review',json=raw_review(card)|{'condition_checked':False}).status_code==422
 assert owner.post('/api/listings/'+l['id']+'/review',json=raw_review(card)|{'cert':'12345678'}).status_code==422
 assert owner.post('/api/listings/'+l['id']+'/review',json=raw_review(card)).status_code==200
 d=owner.get('/api/cards/'+card['id']).json()
 assert d['listings'][0]['match']['condition_key']==RAWKEY


def test_used_unknown_cannot_be_reviewed_as_mint(owner,card,listing_payload):
 l=owner.post('/api/listings',json=raw_listing(listing_payload,raw_condition='Unknown',condition_original='Used')).json()
 assert owner.post('/api/listings/'+l['id']+'/review',json=raw_review(card)).status_code==422


def test_recommendation_exposes_only_matching_sales(owner,card,listing_payload,sale_payload):
 add_raw(owner,card,listing_payload,price=10,shipping=0)
 for n in range(5):
  r=owner.post('/api/sales',json=sale_payload|RAW|{'condition_confirmed':True,'item_price':20,'source_url':f'https://example.com/raw/{n}','transaction_id':f'raw{n}'})
  assert r.status_code==200,r.text
  assert owner.post('/api/sales',json=sale_payload|{'source_url':f'https://example.com/psa/{n}','transaction_id':f'psa{n}'}).status_code==200
 d=owner.get('/api/cards/'+card['id']).json();a=d['listings'][0]['assessment']
 assert a['label']=='Good buying opportunity' and a['market']['reference']==20
 assert a['market']['count']==5 and len(a['market']['excluded'])==5
 assert 'item-only' in a['explanation'] and a['market']['condition_key']==RAWKEY
 assert d['market']['reference']==100
 assert d['best_by_condition'][0]['total']==10
 assert 'could not be checked' in d['psa10_summary']


def test_best_total_excludes_auction_unknown_shipping_and_unavailable(owner,card,listing_payload):
 good=add_raw(owner,card,listing_payload,price=20,shipping=5)
 add_raw(owner,card,listing_payload,url='https://example.com/cheaper-unknown',price=1,shipping=None)
 add_raw(owner,card,listing_payload,url='https://example.com/auction',price=1,listing_type='auction')
 d=owner.get('/api/cards/'+card['id']).json()
 assert d['best_by_condition'][0]['best_listing_id']==good['id']
 assert len(d['best_by_condition'][0]['incomplete_cost_listing_ids'])==1
 assert owner.post('/api/listings/'+good['id']+'/unavailable').status_code==200
 d=owner.get('/api/cards/'+card['id']).json();assert d['best_by_condition'][0]['best_listing_id'] is None


def test_condition_edit_invalidates_review_and_separates_observations(owner,card,listing_payload):
 item=add_raw(owner,card,listing_payload)
 owner.post('/api/listings',json=raw_listing(listing_payload)) # unchanged not repeated history
 d=owner.get('/api/cards/'+card['id']).json();assert len(d['price_observations'])==1
 assert d['listings'][0]['match']['status']=='candidate'
 owner.post('/api/listings',json=listing_payload)
 d=owner.get('/api/cards/'+card['id']).json()
 assert len(d['price_observations'])==2
 assert {o['condition_key'] for o in d['price_observations']}=={RAWKEY,PSA10}
 assert d['market']['count']==0 # asking observations never become completed sales


def test_target_is_condition_specific_and_psa_upgrade_stays_watched(owner,app,card,listing_payload,copy_payload,review_payload):
 unpause(owner)
 owner.put('/api/watchlist',json={'variant_id':card['id'],'target_price':100})
 raw=add_raw(owner,card,listing_payload,price=20)
 assert owner.get('/api/alerts').json()['alerts']==[]
 owner.put('/api/watchlist',json={'variant_id':card['id'],'target_price':100,'targets':{RAWKEY:30}})
 assert len(owner.get('/api/alerts').json()['alerts'])==1
 assert evaluate_alerts(app.state.db)==0
 alerts=owner.get('/api/alerts').json()['alerts'];assert alerts[0]['condition_key']==RAWKEY
 assert owner.post('/api/copies',json=raw_copy(copy_payload)).status_code==200
 # Other raw offers are no longer a collection need, but PSA 10 still is.
 add_raw(owner,card,listing_payload,url='https://example.com/raw-second',price=10)
 assert len(owner.get('/api/alerts').json()['alerts'])==1
 psa=owner.post('/api/listings',json=listing_payload|{'url':'https://example.com/psa-upgrade'}).json()
 assert owner.post('/api/listings/'+psa['id']+'/review',json=review_payload).status_code==200
 assert len(owner.get('/api/alerts').json()['alerts'])==2
 assert any(d['listing']['condition_key']==PSA10 for d in owner.get('/api/deals').json()['deals'])
 assert all(d['listing']['condition_key']!=RAWKEY for d in owner.get('/api/deals').json()['deals'])


def test_seller_preferences_and_budget_fail_closed(owner,card,listing_payload):
 add_raw(owner,card,listing_payload,price=20,seller_country='US',seller_feedback=95)
 unpause(owner,min_seller_feedback=99,seller_countries=['BE'],budget=10)
 d=owner.get('/api/cards/'+card['id']).json();a=d['listings'][0]['assessment']
 assert not a['eligible_for_target'] and not a['within_budget']
 assert 'Seller feedback' in a['explanation'] and 'Seller location' in a['explanation']
 assert d['best_by_condition'][0]['best_listing_id'] is None


def test_raw_copy_csv_round_trip_and_targets_json(owner,app,card,copy_payload):
 first=owner.post('/api/copies',json=raw_copy(copy_payload)).json()
 csv_text=owner.get('/api/export/copies').text
 assert 'RAW' in csv_text
 assert owner.post('/api/import',json={'kind':'copies','csv_text':csv_text,'commit':False}).json()['ok']
 assert len(app.state.db.records('copies'))==1
 assert owner.post('/api/import',json={'kind':'copies','csv_text':csv_text,'commit':True}).json()['ok']
 assert len(app.state.db.records('copies'))==2
 payload={'variant_id':card['id'],'fallback_enabled':True,'fallback_buckets':[RAWKEY],'targets':{RAWKEY:20,PSA10:100}}
 assert owner.put('/api/watchlist',json=payload).status_code==200
 export=owner.get('/api/export/watchlist').text
 assert json.loads(next(csv.DictReader(io.StringIO(export)))['targets'])==payload['targets']
 assert owner.post('/api/import',json={'kind':'watchlist','csv_text':export,'commit':True}).json()['ok']
 assert owner.get('/api/cards/'+card['id']).json()['watch']['targets']==payload['targets']


def test_new_private_endpoints_require_authentication(client,card):
 for path in ['/api/sources','/api/deals','/api/cards/'+card['id']]: assert client.get(path).status_code==401
 assert client.put('/api/sources/pricecharting',json={'token':'synthetic-test-token-that-is-not-real'}).status_code==401
 assert client.post('/api/cards/'+card['id']+'/scan').status_code==401


def test_card_scan_and_heartbeat_honor_pause_and_identity(owner,app,card):
 r=owner.post('/api/cards/'+card['id']+'/scan');assert r.status_code==200,r.text
 result=r.json();assert result['status']=='paused'
 assert owner.get('/api/monitor').json()['last_execution']['checkedAt']==result['checkedAt']
 assert app.state.db.records('listings')==[]


def test_psa_review_certificate_format_is_not_relaxed_by_other_graders(owner,card,listing_payload,review_payload):
 item=owner.post('/api/listings',json=listing_payload|{'cert':''}).json()
 response=owner.post('/api/listings/'+item['id']+'/review',json=review_payload|{'cert':'ABCDEF12'})
 assert response.status_code==422
 assert 'digit' in response.json()['detail']
