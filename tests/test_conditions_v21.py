"""Synthetic condition/grade fixtures: never real prices or market evidence."""
from datetime import date
import pytest
from pydantic import ValidationError
from ember.conditions import *
from ember.models import CopyIn, ListingIn, SaleIn, Preferences, ConditionFields
from ember.matching import screen
from ember.pricing import valuation, acquisition

RAW={'grader':'RAW','grade':None,'raw_condition':'Near Mint','condition_scale':'seller','condition_original':'Near Mint'}
PSA9={'grader':'PSA','grade':9,'designation':'Mint'}

@pytest.mark.parametrize('word,source,want,scale',[
 ('Used','eBay','Unknown','ebay'),('New','eBay','Unknown','ebay'),
 ('NM/M','TCGplayer','Unknown','tcgplayer'),('Near Mint to Mint','Manual','Unknown','seller'),
 ('Near Mint or Better','eBay','Near Mint or Better','ebay'),
 ('Near Mint','TCGplayer','Near Mint','tcgplayer'),('LP','TCGplayer','Lightly Played','tcgplayer'),
 ('EX','Cardmarket','Excellent','cardmarket'),('GD','Cardmarket','Good','cardmarket'),
 ('PL','Cardmarket','Played','cardmarket'),('PO','Cardmarket','Poor','cardmarket'),
 ('Light Played','Cardmarket','Lightly Played','cardmarket'),('NM','Manual','Near Mint','seller'),
 ('seller says excellent perhaps mint','Manual','Unknown','seller')])
def test_mapping_is_explicit_and_preserves_source(word,source,want,scale):
 r=normalize_raw(word,source)
 assert r['condition_original']==word and r['raw_condition']==want and r['condition_scale']==scale


def test_bucket_options_are_unique_and_validate():
 opts=bucket_options(); assert len({o['key'] for o in opts})==len(opts)
 for option in opts:
  c=ConditionFields(**option['fields']).model_dump()
  assert condition_key(c)==option['key']

@pytest.mark.parametrize('title,grader,grade,designation,scale',[
 ('Charmander PSA 9','PSA',9,'Mint','current'),
 ('Charmander PSA Gem Mint 10','PSA',10,'Gem Mint','current'),
 ('Charmander BGS 10 Black Label','BGS',10,'Black Label','current'),
 ('Charmander BGS Pristine 10','BGS',10,'Pristine','current'),
 ('Charmander CGC Gem Mint 10','CGC',10,'Gem Mint','current'),
 ('Charmander CGC Perfect 10','CGC',10,'Perfect','legacy'),
 ('Charmander CGC Pristine 10','CGC',10,'Pristine','unspecified'),
 ('Charmander CGC 9.5','CGC',9.5,'','unspecified')])
def test_seller_grade_inference(title,grader,grade,designation,scale):
 c=infer_condition(title)
 assert (c['grader'],c['grade'],c['designation'],c['grading_scale'])==(grader,grade,designation,scale)


def test_all_special_grades_and_raw_scales_stay_distinct():
 cases=[{'grader':'PSA','grade':10}, {'grader':'BGS','grade':10,'designation':'Black Label'},
  {'grader':'BGS','grade':10,'designation':'Pristine'},
  {'grader':'CGC','grade':10,'designation':'Pristine','grading_scale':'current'},
  {'grader':'CGC','grade':10,'designation':'Pristine','grading_scale':'legacy'},
  RAW,RAW|{'condition_scale':'tcgplayer'},RAW|{'condition_scale':'cardmarket'}]
 assert len({condition_key(c) for c in cases})==len(cases)
 assert sum(is_psa10(c) for c in cases)==1

@pytest.mark.parametrize('fields',[
 {'grader':'PSA','grade':9.5}, {'grader':'RAW','grade':10},
 {'grader':'BGS','grade':10,'designation':'Gem Mint'},
 {'grader':'CGC','grade':10,'designation':'Perfect','grading_scale':'current'},
 {'grader':'CGC','grade':10,'designation':'Gem Mint','grading_scale':'legacy'},
 {'grader':'PSA','grade':9,'designation':'Gem Mint'},
 {'grader':'PSA','grade':8.1}, {'grader':'PSA','grade':10,'raw_condition':'Near Mint'}])
def test_invalid_condition_assertions_rejected(fields):
 with pytest.raises(ValidationError): ConditionFields(**fields)

@pytest.mark.parametrize('fields',[
 {'grader':'UNKNOWN','grade':None}, RAW|{'raw_condition':'Unknown'},
 {'grader':'BGS','grade':10}, {'grader':'CGC','grade':10,'designation':'Pristine','grading_scale':'unspecified'}])
def test_unresolved_buckets_cannot_be_recommended(fields):
 assert not condition_known(fields)
 assert not allowed_condition(fields,Preferences().model_dump())


def test_legacy_psa10_and_per_condition_targets():
 p=Preferences().model_dump(); assert condition_key({})==PSA10
 w={'target_price':100,'targets':{condition_key(RAW):20}}
 assert target_for(RAW,w,p)==20 and target_for(PSA9,w,p) is None
 assert target_for({'grader':'PSA','grade':10},w,p)==100
 assert cert_identity({'grader':'BGS'},'12345678')!=cert_identity({'grader':'PSA'},'12345678')


def test_owning_alternative_never_disables_psa_upgrade(card):
 p=Preferences().model_dump(); vid=card['id']; copies=[RAW|{'variant_id':vid,'status':'Owned'}]
 assert need_listing(vid,{'grader':'PSA','grade':10},copies,p)
 assert not need_listing(vid,RAW,copies,p)
 copies[0]['status']='Ordered'; assert need_listing(vid,{'grader':'PSA','grade':10},copies,p)
 copies.append({'variant_id':vid,'status':'Ordered','grader':'PSA','grade':10})
 assert not need_listing(vid,{'grader':'PSA','grade':10},copies,p)


def test_fallback_override_and_disabled_preferences():
 p=Preferences(fallback_enabled=False).model_dump()
 assert not allowed_condition(RAW,p)
 assert allowed_condition(RAW,p,{'fallback_enabled':True,'fallback_buckets':[condition_key(RAW)]})
 assert not allowed_condition(PSA9,p,{'fallback_enabled':True,'fallback_buckets':[condition_key(RAW)]})

@pytest.mark.parametrize('title,fields',[
 ('Charmander 46/102 Base Set English PSA 10',RAW),
 ('Charmander 46/102 Base Set English PSA 9',{'grader':'PSA','grade':10}),
 ('Charmander 46/102 Base Set English BGS 10 Black Label',{'grader':'BGS','grade':10,'designation':'Pristine'}),
 ('Charmander 46/102 Base Set English CGC Perfect 10',{'grader':'CGC','grade':10,'designation':'Gem Mint','grading_scale':'current'}),
 ('Charmander 46/102 Base Set English raw PSA 10 potential',RAW),
 ('Charmander 46/102 Base Set English raw bundle 2 cards',RAW),
 ('Charmander 46/102 French raw Near Mint',RAW),
 ('Charmander 46/102 English reverse holo raw Near Mint',RAW),
 ('Charmander 46/102 English raw Near Mint',RAW|{'condition_original':'Damaged'})])
def test_conflicting_raw_and_graded_evidence_cannot_be_overridden(card,title,fields):
 assert screen(title,card,condition=fields)['status']=='rejected'

@pytest.mark.parametrize('title,fields',[
 ('Charmander 46/102 Base Set Unlimited English PSA 9',PSA9),
 ('Charmander 46/102 Base Set Unlimited English raw Near Mint',RAW),
 ('Charmander 46/102 Base Set Unlimited English CGC Gem Mint 10',{'grader':'CGC','grade':10,'designation':'Gem Mint','grading_scale':'current'})])
def test_newly_enabled_conditions_are_candidates_not_automatic_matches(card,title,fields):
 assert screen(title,card,condition=fields)['status']=='candidate'


def sales_for(card,fields,count=5,price=100,prefix='same'):
 return [fields|{'id':f'{prefix}-{i}','variant_id':card['id'],'source':'Synthetic test',
  'source_url':f'https://example.com/{prefix}/{i}','transaction_key':f'{prefix}-{i}',
  'sold_date':date.today().isoformat(),'completed':True,'price_disclosed':True,
  'exact_variant_confirmed':True,'condition_confirmed':True,'item_price':price,'currency':'EUR'} for i in range(count)]


def test_valuation_cannot_mix_grades_platforms_or_raw_conditions(card):
 p=Preferences().model_dump(); own=sales_for(card,RAW,price=20)
 other=sales_for(card,{'grader':'PSA','grade':10},price=100,prefix='psa')
 other+=sales_for(card,RAW|{'condition_scale':'tcgplayer'},price=80,prefix='platform')
 other+=sales_for(card,RAW|{'raw_condition':'Damaged'},price=2,prefix='damage')
 result=valuation(card['id'],own+other,p,None,condition=RAW)
 assert result['reference']==20 and result['count']==5 and len(result['excluded'])==15
 result=valuation(card['id'],own+other,p,None)
 assert result['reference']==100 and result['count']==5


def test_valuation_cgc_eras_and_bgs_designations_do_not_mix(card):
 p=Preferences().model_dump()
 legacy={'grader':'CGC','grade':10,'designation':'Pristine','grading_scale':'legacy'}
 current=legacy|{'grading_scale':'current'}
 result=valuation(card['id'],sales_for(card,legacy,price=100)+sales_for(card,current,price=200,prefix='now'),p,None,condition=current)
 assert result['reference']==200 and result['count']==5


def test_thin_or_unconfirmed_alternative_sales_remain_insufficient(card):
 p=Preferences().model_dump(); sales=sales_for(card,RAW,count=4)
 assert valuation(card['id'],sales,p,None,condition=RAW)['reference'] is None
 sales+=sales_for(card,RAW,count=1,prefix='unconfirmed')
 sales[-1]['condition_confirmed']=False
 assert valuation(card['id'],sales,p,None,condition=RAW)['count']==4

@pytest.mark.parametrize('override,unknown',[
 ({'shipping':None},'shipping'),({'fees':None},'fees'),({'import_cost':None},'import_cost'),
 ({'delivery_eligible':None},'delivery eligibility'),({'delivery_eligible':False},'delivery unavailable to your country'),
 ({'currency':'USD'},'current exchange rate'),({'listing_type':'auction'},'final auction price')])
def test_unknown_or_auction_costs_never_turn_into_final_prices(listing_payload,override,unknown):
 result=acquisition(listing_payload|override,Preferences().model_dump(),None)
 assert result['total'] is None and unknown in result['unknown']
