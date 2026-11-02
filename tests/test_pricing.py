from datetime import date,datetime,timedelta,timezone
import pytest
from ember.models import Preferences
from ember.db import now
from ember.pricing import acquisition,valuation,budget_state,assess,convert

@pytest.fixture
def prefs():return Preferences().model_dump()

def sales(payload,values):
    return [payload|{'grader':'PSA','grade':10,'id':str(i),'transaction_key':str(i),'item_price':v,'source_url':f'https://example.com/sale/{i}'} for i,v in enumerate(values)]

def listing(payload):return payload|{'status':'active','listing_type':'fixed','checked_at':now()}

def test_sparse_evidence_no_valuation(sale_payload,prefs):
    v=valuation(sale_payload['variant_id'],sales(sale_payload,[100,105]),prefs,None)
    assert v['reference'] is None and v['count']==2

def test_outlier_transparency(sale_payload,prefs):
    v=valuation(sale_payload['variant_id'],sales(sale_payload,[98,100,101,102,103,10000]),prefs,None)
    assert v['reference']==101 and v['count']==5
    assert 'outlier' in v['excluded'][0]['excluded_reason']
    assert 'not a confidence interval' in v['method']

@pytest.mark.parametrize('change',[{'price_disclosed':False},{'completed':False},{'exact_variant_confirmed':False},{'grade':9},{'grader':'CGC'},{'sold_date':'2099-01-01'},{'sold_date':'2000-01-01'}])
def test_bad_evidence_excluded(sale_payload,prefs,change):
    s=sales(sale_payload,[100])[0]|change
    v=valuation(s['variant_id'],[s],prefs,None)
    assert v['count']==0 and len(v['excluded'])==1

def test_duplicate_transaction_and_cert_not_double_counted(sale_payload,prefs):
    ss=sales(sale_payload,[100,100,100])
    ss[1]['transaction_key']='0'
    ss[0]['cert']=ss[2]['cert']='90000001'
    v=valuation(sale_payload['variant_id'],ss,prefs,None)
    assert v['count']==1 and len(v['excluded'])==2

def test_recency_changes_reference(sale_payload,prefs):
    ss=sales(sale_payload,[100,101,102,120,121])
    for s in ss[:3]:s['sold_date']=(date.today()-timedelta(days=120)).isoformat()
    v=valuation(sale_payload['variant_id'],ss,prefs,None)
    assert v['reference']==120

@pytest.mark.parametrize('field',['shipping','fees','import_cost'])
def test_unknown_cost_not_zero(listing_payload,prefs,field):
    cost=acquisition(listing_payload|{field:None},prefs,None)
    assert cost['total'] is None and field in cost['unknown']

def test_destination_change_invalidates_total(listing_payload,prefs):
    assert acquisition(listing_payload,prefs|{'country':'US'},None)['total'] is None

def test_currency_conversion_requires_fresh_rate():
    stale={'date':'2000-01-01','rates':{'EUR':1,'USD':1.2}}
    assert convert(10,'USD','EUR',stale) is None
    assert convert(10,'EUR','EUR',None)==10
    assert convert(float('nan'),'EUR','EUR',None) is None
    current={'date':date.today().isoformat(),'rates':{'EUR':1,'USD':1.2}}
    assert convert(120,'USD','EUR',current)==100


def test_local_calendar_sales_and_fx_are_valid_before_utc_midnight(monkeypatch,sale_payload,prefs):
    import ember.pricing as pricing
    class LocalCalendar(date):
        @classmethod
        def today(cls):
            return cls(2026,11,3)
    class UtcClock(datetime):
        @classmethod
        def now(cls,tz=None):
            instant=cls(2026,11,2,23,30,tzinfo=timezone.utc)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    monkeypatch.setattr(pricing,'date',LocalCalendar)
    monkeypatch.setattr(pricing,'datetime',UtcClock)
    evidence=sales(sale_payload|{'sold_date':'2026-11-03'},[100]*5)
    evidence.append(evidence[0]|{'id':'future','transaction_key':'future','sold_date':'2026-11-04'})
    result=pricing.valuation(sale_payload['variant_id'],evidence,prefs,None)
    assert result['count']==5 and result['reference']==100
    assert len(result['excluded'])==1
    rates={'date':'2026-11-03','rates':{'EUR':1,'USD':1.2}}
    assert pricing.convert(120,'USD','EUR',rates)==100
    assert pricing.convert(120,'USD','EUR',rates|{'date':'2026-11-04'}) is None

def test_good_price_exposes_evidence(sale_payload,listing_payload,prefs):
    market=valuation(sale_payload['variant_id'],sales(sale_payload,[100]*5),prefs,None)
    a=assess(listing(listing_payload),{'status':'verified','confidence':'owner-reviewed'},market,prefs,None,budget_state([],prefs,None))
    assert a['label']=='Good buying opportunity' and a['discount_pct']==25
    assert len(a['market']['included'])==5 and a['cost']['total']==75

@pytest.mark.parametrize('change',[{'listing_type':'auction'},{'shipping':None},{'status':'unavailable'},{'checked_at':'2000-01-01T00:00:00+00:00'},{'end_at':'2000-01-01T00:00:00+00:00'}])
def test_no_bargain_for_unusable_observation(sale_payload,listing_payload,prefs,change):
    market=valuation(sale_payload['variant_id'],sales(sale_payload,[100]*5),prefs,None)
    a=assess(listing(listing_payload)|change,{'status':'verified'},market,prefs,None,budget_state([],prefs,None))
    assert a['label']=='Insufficient data' and not a['eligible_for_target']

def test_target_possible_without_valuation(sale_payload,listing_payload,prefs):
    market=valuation(sale_payload['variant_id'],[],prefs,None)
    a=assess(listing(listing_payload),{'status':'verified'},market,prefs,None,budget_state([],prefs,None))
    assert a['eligible_for_target'] and a['label']=='Insufficient data'

def test_budget_counts_ordered_and_unknown(copy_payload,prefs):
    p=prefs|{'budget':100}
    b=budget_state([copy_payload|{'status':'Ordered'}],p,None)
    assert b['remaining']==15
    b=budget_state([copy_payload|{'shipping':None}],p,None)
    assert b['remaining'] is None and b['unknown_cost_copies']==1
