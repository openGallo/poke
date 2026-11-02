"""Synthetic provider contracts only; none of these prices are real observations."""
import asyncio
import copy
import json
import httpx
import pytest
from ember import aggregates, public_guides
from ember.models import PublicGuideRequest
from ember.providers import SourceError
from ember.db import dumps


def body():
    return {'id':'base1-46','localId':'46','name':'Charmander','set':{'id':'base1'},'pricing':{
        'cardmarket':{'unit':'EUR','updated':'2026-01-01T00:00:00Z','low':10,'avg7':20,'avg7-holo':30,'trend':None,'low-holo':0},
        'tcgplayer':{'unit':'USD','updated':'2026-01-02T00:00:00Z','normal':{'marketPrice':25,'lowPrice':15,'unknown':999},'arbitrary':{'marketPrice':999}}}}


def run(db,card,handler,**kwargs):
    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await public_guides.refresh_guides(db,card,PublicGuideRequest(provider_id='base1-46',base_card_confirmed=True,**kwargs),client)
    return asyncio.run(execute())


def test_free_guides_cache_dates_currencies_and_no_false_transactions(owner,app,card):
    calls=[]
    def handler(req):
        calls.append(req)
        assert req.url.host=='api.tcgdex.net' and req.url.path=='/v2/en/cards/base1-46'
        return httpx.Response(200,json=body())
    result=run(app.state.db,card,handler)
    assert not result['cached'] and len(result['observations'])==5
    assert {x['currency'] for x in result['observations']}=={'USD','EUR'}
    assert all(x['sample_count'] is None and x['sale_dates'] is None for x in result['observations'])
    assert result['observations'][0]['provider_updated_at']=='2026-01-01T00:00:00Z'
    assert run(app.state.db,card,handler)['cached'] and len(calls)==1
    detail=owner.get('/api/cards/'+card['id']).json()
    assert len(detail['aggregate_observations'])==5 and detail['market']['count']==0 and not detail['listings']
    aggregates.disconnect(app.state.db)
    assert len(app.state.db.rows('SELECT * FROM aggregates'))==5, 'Unrelated provider disconnect must preserve free guides'


@pytest.mark.parametrize('change',[{'id':'base1-47'},{'name':'Charmeleon'},{'localId':'47'},{'set':{'id':'different'}}])
def test_guide_identity_conflicts_not_saved(app,card,change):
    with pytest.raises(SourceError) as exc:
        run(app.state.db,card,lambda _:httpx.Response(200,json=body()|change))
    assert exc.value.status=='identity_mismatch' and not app.state.db.rows('SELECT * FROM aggregates')


def test_empty_guide_is_explicit_and_does_not_change_listings(app,card):
    result=run(app.state.db,card,lambda _:httpx.Response(200,json=body()|{'pricing':{}}))
    assert result['status']=='no_guide_data' and result['observations']==[]
    assert not app.state.db.records('listings')


def test_guide_access_failure_does_not_invent_prices(app,card):
    with pytest.raises(SourceError) as exc:
        run(app.state.db,card,lambda _:httpx.Response(403))
    assert exc.value.status=='access_error'
    assert app.state.db.get('tcgdex_guides_status')['status']=='access_error'
    assert not app.state.db.rows('SELECT * FROM aggregates')


def test_public_guide_api_requires_owner_mapping_and_rejects_arbitrary_urls(owner,app,card):
    path='/api/cards/'+card['id']+'/public-guides'
    assert owner.post(path,json={'provider_id':'base1-46'}).status_code==422
    assert owner.post(path,json={'provider_id':'https://attacker.invalid','base_card_confirmed':True}).status_code==422
    source=next(x for x in owner.get('/api/sources').json()['sources'] if x['id']=='tcgdex_guides')
    assert source['state']['status']=='not_checked'


def test_public_guide_numeric_and_currency_validation(card):
    data=body();data['pricing']['tcgplayer']['unit']='EUR';data['pricing']['cardmarket'].update({'avg1':True,'avg30':'nan','avg':-1})
    rows=public_guides.parse_guides(data,card['id'],'https://api.tcgdex.net/v2/en/cards/base1-46','2026-01-01T00:00:00Z')
    assert len(rows)==3 and all(r['currency']=='EUR' for r in rows)
