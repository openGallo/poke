import math
import pytest
from pydantic import ValidationError
from ember.models import Variant, CopyIn, ListingIn, SaleIn, Preferences, canonical_url, public_url
from ember.matching import screen
from ember.catalogue import from_tcgdex

@pytest.mark.parametrize('change',[{'grader':'CGC'},{'grade':9},{'grade':9.5},{'psa10_confirmed':False},{'cert':''},{'cert':'abc'},{'purchase_price':float('nan')},{'purchase_price':-1},{'currency':'XYZ'},{'purchase_date':'2099-01-01'},{'extra_secret':'no'}])
def test_invalid_ownership_rejected(copy_payload,change):
    with pytest.raises(ValidationError):CopyIn.model_validate(copy_payload|change)

def test_ordered_cert_optional(copy_payload):
    assert CopyIn.model_validate(copy_payload|{'status':'Ordered','cert':''}).cert==''

def test_stable_identifier_zero_padding_and_metadata(card):
    a=Variant.model_validate(card)
    b=Variant.model_validate(card|{'id':'','number':'046/0102','notes':'Metadata changed','year':2000})
    assert a.id==b.id
    c=Variant.model_validate(card|{'id':'','finish':'reverse-holo'})
    assert a.id!=c.id

def test_user_cannot_force_identifier(card):
    with pytest.raises(ValidationError):Variant.model_validate(card|{'id':'arbitrary'})

def test_unrelated_card_excluded(card):
    with pytest.raises(ValidationError):Variant.model_validate(card|{'name':'Pikachu'})
    assert Variant.model_validate(card|{'name':'Pikachu','artwork_only':True}).artwork_only

@pytest.mark.parametrize('url',['http://example.com','https://localhost/','https://127.0.0.1/','https://[::1]/','https://169.254.169.254/','https://example.com:8080/','https://name:password@example.com/','javascript:alert(1)'])
def test_unsafe_url_rejected(url):
    with pytest.raises(ValueError):public_url(url)

def test_url_dedup_preserves_lot_identity():
    assert canonical_url('https://www.ebay.fr/itm/title/123456789012?utm_source=x')=='https://www.ebay.com/itm/123456789012'
    assert canonical_url('https://www.ebay.com.evil.example/itm/123456789012').startswith('https://www.ebay.com.evil.example')
    assert canonical_url('https://example.com/sale?lot=1')!=canonical_url('https://example.com/sale?lot=2')

@pytest.mark.parametrize('bad',['PSA 9.5','PSA 10 potential','PSA 10 candidate','PSA 10?','not PSA 10','raw PSA 10','PSA 10 bundle','PSA 10 lot','PSA 10 BGS 10','PSA 10 replica'])
def test_rejects_ineligible_titles(card,bad):
    assert screen('Charmander 46/102 Base Set Unlimited English '+bad,card)['status']=='rejected'

@pytest.mark.parametrize('title',[
 'Charmander 46/102 Base Set French PSA 10',
 'Charmander 46/102 Base Set 1st edition English PSA 10',
 'Charmander 46/102 Base Set Shadowless English PSA 10',
 'Charmander 46/102 Base Set Reverse Holo English PSA 10',
 'Charmander 46/102 Base Set Jumbo English PSA 10',
 'Charmander 46/102 Base Set Pokemon Center English PSA 10',
 'Charmander 46/100 Base Set English PSA 10',
 'Charmander #47 Base Set English PSA 10',
 'Charmander 46/102 Base Set English Charizard PSA 10',
 "Blaine's Charmander 46/102 Base Set English PSA 10",
 'Charmander 46/102 Base Set Master Ball English PSA 10',
 'Charmander delta 46/102 Base Set English PSA 10',
])
def test_rejects_variant_contradictions(card,title):
    assert screen(title,card)['status']=='rejected'

def test_good_title_is_only_a_candidate(card,listing_payload):
    result=screen(listing_payload['title'],card)
    assert result['status']=='candidate'
    assert result['confidence']=='unverified'

@pytest.mark.parametrize('aspects',[{'Grade':'9'},{'Language':'Japanese'},{'Professional Grader':'CGC'}])
def test_structured_conflicts(card,listing_payload,aspects):
    assert screen(listing_payload['title'],card,aspects)['status']=='rejected'

def test_hidden_offer_not_known_sale(sale_payload):
    with pytest.raises(ValidationError):SaleIn.model_validate(sale_payload|{'price_disclosed':False})
    assert SaleIn.model_validate(sale_payload|{'price_disclosed':False,'item_price':None}).item_price is None

def test_catalogue_sync_retains_distinct_foils():
    card={'id':'sv-test-004','name':'Charmander','dexId':[4],'set':{'id':'sv-test','name':'Test set'},'localId':'004','variants':[{'type':'reverse','foil':'pokeball'},{'type':'reverse','foil':'masterball'}]}
    rows=from_tcgdex(card,'en',{})
    assert len({v['id'] for v in rows})==2
    assert all(v['identity_status']=='provisional' for v in rows)

def test_pocket_excluded():
    assert from_tcgdex({'id':'test','name':'Charmander','set':{'id':'pocket'}},'en',{'serie':{'id':'tcgp'}})==[]


def test_base_set_two_title_is_not_base_set_one(card):
    from ember.matching import screen
    assert screen('Charmander Base Set 2 46/102 English PSA 10',card)['status']=='rejected'


@pytest.mark.parametrize("foil", ["Cosmos", "Cosmic", "Mirage", "Cracked Ice"])
def test_special_foil_not_a_standard_reverse(card, foil):
    v = card | {"finish": "reverse-holo"}
    title = f"Charmander 46/102 Base Set English {foil} Reverse Holo PSA 10"
    assert screen(title, v)["status"] == "rejected"


@pytest.mark.parametrize("aspects", [
    {"Card Number": "47"}, {"Card Number": "46/100"},
    {"Edition": "1st edition"}, {"Card Size": "Jumbo"},
])
def test_structured_identity_contradictions(card, listing_payload, aspects):
    assert screen(listing_payload["title"], card, aspects)["status"] == "rejected"


def test_structured_equivalent_number_is_only_a_candidate(card, listing_payload):
    result = screen(listing_payload["title"], card, {"Card Number": "046/0102"})
    assert result["status"] == "candidate"


def test_matching_documented_foil_still_needs_review(card):
    v = card | {"finish": "mirage-holo"}
    assert screen("Charmander 46/102 Base Set English Mirage Holo PSA 10", v)["status"] == "candidate"
