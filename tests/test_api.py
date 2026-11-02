import csv
import io
import json
from datetime import date
from dataclasses import replace
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from ember.main import create_app
from ember import security
from ember.db import dumps
from conftest import TEST_PASSWORD


def test_private_routes_require_authentication(client):
    for path in ['/api/state','/api/deals','/api/alerts','/api/export/copies','/api/monitor','/api/photos/no-such-image']:
        assert client.get(path).status_code==401
    assert client.get('/').status_code==200
    assert client.get('/healthz').json()['status']=='ok'
    assert client.get('/api/state',headers={'Host':'evil.example'}).status_code==400


def test_login_csrf_cookies_and_logout(client):
    assert client.post('/api/login',json={'password':'wrong'}).status_code==401
    r=client.post('/api/login',json={'password':TEST_PASSWORD})
    assert 'HttpOnly' in r.headers['set-cookie'] and 'SameSite=strict' in r.headers['set-cookie']
    assert client.post('/api/monitor',json={}).status_code==403
    client.headers['X-CSRF-Token']=r.json()['csrf']
    assert client.post('/api/monitor',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/logout').status_code==200
    assert client.get('/api/state').status_code==401


def test_password_validation_never_reflects_secret(client):
    token='do-not-reflect-this-secret'
    r=client.post('/api/login',json={'password':token,'unknown':token})
    assert r.status_code==422 and token not in r.text


def test_rate_limit(client):
    codes=[client.post('/api/login',json={'password':'wrong'}).status_code for _ in range(9)]
    assert codes[-1]==429


def test_new_collection_empty_and_sources_honest(owner):
    s=owner.get('/api/state').json()
    assert s['reconstructed'] and s['copies']==[] and s['watchlist']==[]
    assert s['completion']['owned']==0 and s['coverage']['seed']['complete'] is False
    assert s['sources']['ebay']['status']=='missing_credentials'
    assert s['preferences']['paused'] is True
    assert owner.get('/api/deals').json()['deals']==[]


def test_persistence_restart_and_unique_completion(owner,config,copy_payload):
    assert owner.post('/api/copies',json=copy_payload).status_code==200
    assert owner.post('/api/copies',json=copy_payload|{'cert':'90000003'}).status_code==200
    s=owner.get('/api/state').json()
    assert len(s['copies'])==2 and s['completion']['owned']==1
    cookies=dict(owner.cookies)
    with TestClient(create_app(config)) as again:
        again.cookies.update(cookies)
        s=again.get('/api/state').json()
        assert len(s['copies'])==2 and s['completion']['owned']==1


def test_duplicate_certificate_and_foreign_key_rejected(owner,copy_payload):
    assert owner.post('/api/copies',json=copy_payload).status_code==200
    assert owner.post('/api/copies',json=copy_payload).status_code==409
    assert owner.post('/api/copies',json=copy_payload|{'variant_id':'missing'}).status_code==404
    assert len(owner.get('/api/state').json()['copies'])==1


def test_provisional_cannot_accept_ownership(owner,copy_payload):
    provisional=next(v for v in owner.get('/api/state').json()['variants'] if v['identity_status']=='provisional')
    assert owner.post('/api/copies',json=copy_payload|{'variant_id':provisional['id']}).status_code==422


def test_ordered_does_not_count_until_arrival(owner,copy_payload):
    r=owner.post('/api/copies',json=copy_payload|{'status':'Ordered','cert':''})
    assert r.status_code==200
    s=owner.get('/api/state').json()
    assert s['completion']['owned']==0 and s['completion']['ordered']==1
    assert owner.put('/api/copies/'+r.json()['id'],json=copy_payload).status_code==200
    assert owner.get('/api/state').json()['completion']['owned']==1


def test_edit_and_delete_copy(owner,copy_payload):
    ident=owner.post('/api/copies',json=copy_payload).json()['id']
    assert owner.put('/api/copies/'+ident,json=copy_payload|{'notes':'Edited test record'}).status_code==200
    assert owner.get('/api/state').json()['copies'][0]['notes']=='Edited test record'
    assert owner.delete('/api/copies/'+ident).status_code==200
    assert not owner.get('/api/state').json()['copies']


def test_slab_photo_private_and_reencoded(owner,copy_payload,app):
    ident=owner.post('/api/copies',json=copy_payload).json()['id']
    raw=io.BytesIO();Image.new('RGB',(24,36)).save(raw,format='PNG')
    r=owner.post('/api/copies/'+ident+'/photo',files={'file':('test.png',raw.getvalue(),'image/png')})
    assert r.status_code==200
    key=owner.get('/api/state').json()['copies'][0]['photo_key']
    photo=owner.get('/api/photos/'+key)
    assert photo.headers['content-type']=='image/jpeg'
    with TestClient(app) as anon:assert anon.get('/api/photos/'+key).status_code==401
    assert owner.post('/api/copies/'+ident+'/photo',files={'file':('bad.svg',b'<svg/>','image/svg+xml')}).status_code in {415,422}
    assert owner.delete('/api/copies/'+ident).status_code==200
    assert owner.get('/api/photos/'+key).status_code==404


def test_review_cannot_override_contradictory_grade(owner,listing_payload,review_payload):
    l=owner.post('/api/listings',json=listing_payload|{'grader':'PSA','grade':10,'title':listing_payload['title'].replace('PSA 10','PSA 9')}).json()
    assert l['match']['status']=='rejected'
    assert owner.post('/api/listings/'+l['id']+'/review',json=review_payload).status_code==422


def test_review_requires_all_checks(owner,listing_payload,review_payload):
    l=owner.post('/api/listings',json=listing_payload).json()
    assert owner.post('/api/listings/'+l['id']+'/review',json=review_payload|{'photo_checked':False}).status_code==422
    assert owner.post('/api/listings/'+l['id']+'/review',json=review_payload|{'cert':'99999999'}).status_code==422
    assert owner.post('/api/listings/'+l['id']+'/review',json=review_payload).json()['status']=='verified'


def test_reobservation_clears_review(owner,card,listing_payload,review_payload):
    l=owner.post('/api/listings',json=listing_payload).json()
    owner.post('/api/listings/'+l['id']+'/review',json=review_payload)
    owner.post('/api/listings',json=listing_payload|{'price':60})
    l=owner.get('/api/cards/'+card['id']).json()['listings'][0]
    assert l['match']['status']=='candidate'


def test_end_to_end_evidence_and_deal(owner,card,listing_payload,sale_payload,review_payload):
    l=owner.post('/api/listings',json=listing_payload).json()
    owner.post('/api/listings/'+l['id']+'/review',json=review_payload)
    for i in range(5):
        r=owner.post('/api/sales',json=sale_payload|{'source_url':f'https://example.com/sales/{i}','transaction_id':str(i)})
        assert r.status_code==200,r.text
    d=owner.get('/api/cards/'+card['id']).json()
    assert d['market']['count']==5 and len(d['market']['included'])==5
    assert d['listings'][0]['assessment']['label']=='Good buying opportunity'
    assert len(owner.get('/api/deals').json()['deals'])==1


def test_ebay_same_transaction_id_cannot_inflate(owner,sale_payload):
    a=sale_payload|{'source_url':'https://www.ebay.fr/itm/123456789012'}
    assert owner.post('/api/sales',json=a).status_code==200
    assert owner.post('/api/sales',json=a|{'transaction_id':'different-label'}).status_code==409


def test_country_change_clears_old_delivery_costs(owner,card,listing_payload):
    owner.post('/api/listings',json=listing_payload)
    prefs=owner.get('/api/state').json()['preferences'];prefs['country']='US'
    assert owner.put('/api/settings',json=prefs).status_code==200
    l=owner.get('/api/cards/'+card['id']).json()['listings'][0]
    assert l['shipping'] is None and l['assessment']['cost']['total'] is None


def test_csv_preview_atomic_commit_and_roundtrip(owner,copy_payload):
    output=io.StringIO();w=csv.DictWriter(output,fieldnames=list(copy_payload));w.writeheader();w.writerow(copy_payload)
    text=output.getvalue()
    r=owner.post('/api/import',json={'kind':'copies','csv_text':text})
    assert r.status_code==200 and r.json()['ok'] and not r.json()['committed']
    assert not owner.get('/api/state').json()['copies']
    r=owner.post('/api/import',json={'kind':'copies','csv_text':text,'commit':True})
    assert r.json()['committed']
    exported=owner.get('/api/export/copies').text
    assert '90000001' in exported and 'psa10_confirmed' in exported
    assert not owner.post('/api/import',json={'kind':'copies','csv_text':text,'commit':True}).json()['ok']
    assert len(owner.get('/api/state').json()['copies'])==1


def test_csv_malformed_and_duplicate_batch(owner,copy_payload):
    r=owner.post('/api/import',json={'kind':'watchlist','csv_text':'variant_id,priority\na,1,extra\n','commit':True})
    assert r.status_code==200 and not r.json()['ok']
    output=io.StringIO();w=csv.DictWriter(output,fieldnames=list(copy_payload));w.writeheader();w.writerow(copy_payload);w.writerow(copy_payload)
    r=owner.post('/api/import',json={'kind':'copies','csv_text':output.getvalue(),'commit':True})
    assert not r.json()['ok'] and not owner.get('/api/state').json()['copies']


def test_export_formula_escape(owner,copy_payload):
    owner.post('/api/copies',json=copy_payload|{'seller':'=HYPERLINK("https://example.com")'})
    rows=list(csv.DictReader(io.StringIO(owner.get('/api/export/copies').text)))
    assert rows[0]['seller'].startswith("'=")


def test_monitor_service_limited_and_readback(client,config):
    h={'Authorization':'Bearer '+config.monitor_token}
    assert client.get('/api/state',headers=h).status_code==401
    result=client.post('/api/monitor',json={'force':True},headers=h)
    assert result.status_code==200 and result.json()['status']=='paused'
    proof=client.get('/api/monitor',headers=h).json()
    assert proof['last_execution']['checkedAt']==result.json()['checkedAt']

@pytest.mark.parametrize('body',[[],None,{'force':'yes'},{'unexpected':True}])
def test_monitor_bad_json_safe(owner,body):
    assert owner.post('/api/monitor',content=json.dumps(body),headers={'Content-Type':'application/json'}).status_code==422


def test_encryption_and_state_secrecy(owner,app,config):
    secret='synthetic-private-provider-secret'
    ciphertext=security.encrypt(config,dumps({'client_id':'test','client_secret':secret}))
    app.state.db.put('ebay_credentials',ciphertext)
    assert secret not in ciphertext and secret in security.decrypt(config,ciphertext)
    assert secret not in owner.get('/api/state').text
    assert ciphertext not in owner.get('/api/state').text


def test_password_rotation_invalidates_existing_session(owner,config,password_hash):
    new=replace(config,password_hash=security.PH.hash('Different synthetic test password'))
    with TestClient(create_app(new)) as other:
        other.cookies.update(dict(owner.cookies))
        assert other.get('/api/state').status_code==401


def test_export_roundtrip_preserves_literal_grade_and_apostrophe(owner,config,copy_payload,tmp_path):
    item=copy_payload|{'seller':"'Literal apostrophe",'notes':'=literal spreadsheet-like text'}
    assert owner.post('/api/copies',json=item).status_code==200
    exported=owner.get('/api/export/copies').text
    with TestClient(create_app(replace(config,data_dir=tmp_path/'second-db'))) as other:
        r=other.post('/api/login',json={'password':TEST_PASSWORD});other.headers['X-CSRF-Token']=r.json()['csrf']
        r=other.post('/api/import',json={'kind':'copies','csv_text':exported,'commit':True})
        assert r.status_code==200 and r.json()['committed'],r.text
        row=other.get('/api/state').json()['copies'][0]
        assert row['grade']==10 and row['seller']==item['seller'] and row['notes']==item['notes']


def test_edition_and_size_scope(owner):
    p=owner.get('/api/state').json()['preferences']
    p.update(editions=['1st edition'],sizes=['standard'])
    assert owner.put('/api/settings',json=p).status_code==200
    rows=owner.get('/api/state').json()['variants']
    assert rows and all(v['edition']=='1st edition' and v['size']=='standard' for v in rows)
