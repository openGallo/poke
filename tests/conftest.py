"""All test data is synthetic and confined to pytest's temporary directory."""
from dataclasses import replace
from datetime import date
import pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from ember.config import Config
from ember.main import create_app
from ember.security import PH

TEST_PASSWORD='Synthetic test password -- never production'

@pytest.fixture(scope='session')
def password_hash():
    return PH.hash(TEST_PASSWORD)

@pytest.fixture
def config(tmp_path,password_hash):
    return Config(data_dir=tmp_path/'private-runtime',password_hash=password_hash,encryption_key=Fernet.generate_key().decode(),public_url='http://testserver',scheduler=False,testing=True,monitor_token='isolated-service-token-not-production')

@pytest.fixture
def app(config):
    return create_app(config)

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c

@pytest.fixture
def owner(client):
    r=client.post('/api/login',json={'password':TEST_PASSWORD})
    assert r.status_code==200
    client.headers['X-CSRF-Token']=r.json()['csrf']
    return client

@pytest.fixture
def card(app):
    return next(v for v in app.state.db.records('variants') if v['set_code']=='base1' and v['language']=='en' and v['edition']=='unlimited' and v['print_run']=='standard' and v['size']=='standard')

@pytest.fixture
def copy_payload(card):
    return {'variant_id':card['id'],'status':'Owned','cert':'90000001','psa10_confirmed':True,'purchase_price':80,'shipping':5,'fees':0,'import_cost':0,'currency':'EUR','purchase_date':date.today().isoformat(),'seller':'SYNTHETIC TEST SELLER','notes':'TEST ONLY'}

@pytest.fixture
def listing_payload(card):
    return {'variant_id':card['id'],'title':'Charmander 46/102 Base Set Unlimited English PSA 10','url':'https://www.ebay.com/itm/123456789012','price':70,'currency':'EUR','shipping':5,'fees':0,'import_cost':0,'destination_country':'BE','delivery_eligible':True,'cert':'90000002','notes':'SYNTHETIC TEST ONLY'}

@pytest.fixture
def sale_payload(card):
    return {'variant_id':card['id'],'source':'Synthetic test source','source_url':'https://example.com/sales/1','transaction_id':'test-1','sold_date':date.today().isoformat(),'item_price':100,'currency':'EUR','price_disclosed':True,'completed':True,'exact_variant_confirmed':True,'notes':'TEST ONLY'}

@pytest.fixture
def review_payload(card):
    return {'variant_id':card['id'],'identity_confirmed':True,'photo_checked':True,'label_checked':True,'cert_checked':True,'cert':'90000002','notes':'Synthetic fixture attestation; never actual market evidence.'}
