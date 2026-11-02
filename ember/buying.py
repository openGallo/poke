"""One condition-aware comparison service shared by cards, deals and dashboard."""
import json
from datetime import datetime, timezone
from .db import now
from .pricing import valuation, assess, budget_state, convert
from .conditions import (PSA10, condition_key, condition_label, is_psa10, allowed_condition,
                         need_listing, target_for, condition_rank, cert_identity)


def comparison(db,vid,prefs):
    fx=db.get('fx'); sales=db.records('sales'); copies=db.records('copies')
    watch=next((w for w in db.records('watchlist') if w['variant_id']==vid),None)
    budget=budget_state(copies,prefs,fx); markets={}; listings=[]
    for r in db.rows('SELECT l.data AS listing,m.data AS matching FROM listings l JOIN listing_matches m ON m.listing_id=l.id WHERE m.variant_id=?',(vid,)):
        l=json.loads(r['listing']); m=json.loads(r['matching']); key=condition_key(l)
        if key not in markets: markets[key]=valuation(vid,sales,prefs,fx,condition=l)
        assessment=assess(l,m,markets[key],prefs,fx,budget)
        eligible=allowed_condition(l,prefs,watch)
        needed=need_listing(vid,l,copies,prefs,watch)
        target=convert(target_for(l,watch,prefs),(watch or {}).get('currency',prefs['currency']),prefs['currency'],fx)
        assessment.update(preference_eligible=eligible,needed_for_collection=needed,
            target_price=target,within_target=bool(eligible and needed and assessment['eligible_for_target'] and target is not None and assessment['cost']['total']<=target))
        listings.append({**l,'condition_key':key,'condition_label':condition_label(l),'match':m,'assessment':assessment,
                         'condition_rank':condition_rank(l,prefs,watch)})
    for sale in sales:
        key=condition_key(sale)
        if sale['variant_id']==vid and key not in markets: markets[key]=valuation(vid,sales,prefs,fx,condition=sale)
    if PSA10 not in markets: markets[PSA10]=valuation(vid,sales,prefs,fx)
    # All verified cross-postings stay visible on the card; canonical grouping never merges raw copies.
    for l in listings:
        cert=l.get('match',{}).get('cert') or l.get('cert')
        l['cross_post_group']=cert_identity(l,cert) if cert and l['match'].get('status')=='verified' else None
    listings.sort(key=lambda l:(l['condition_rank'],l['listing_type']=='auction',l['assessment']['cost']['total'] is None,l['assessment']['cost']['total'] if l['assessment']['cost']['total'] is not None else float('inf')))
    best=[]
    for key in dict.fromkeys(l['condition_key'] for l in listings):
        group=[l for l in listings if l['condition_key']==key]
        available=[l for l in group if l['assessment']['eligible_for_target'] and l['assessment']['preference_eligible']]
        # eligibility includes complete costs, freshness, owner review, destination and budget.
        winner=min(available,key=lambda l:l['assessment']['cost']['total']) if available else None
        bounds=[l for l in group if l['status']=='active' and l['listing_type']=='fixed' and l['assessment']['cost']['total'] is None]
        best.append({'condition_key':key,'condition_label':group[0]['condition_label'],
                     'best_listing_id':winner['id'] if winner else None,
                     'total':winner['assessment']['cost']['total'] if winner else None,
                     'incomplete_cost_listing_ids':[l['id'] for l in bounds],
                     'message':'Lowest confirmed eligible total among recorded sources, within your budget.' if winner else 'No reviewed, current, deliverable offer with a complete total within your preferences and budget.'})
    psa=[l for l in listings if is_psa10(l) and l['status']=='active']
    reviewed=[l for l in psa if l['match'].get('status')=='verified']
    coverage=db.get('scan_coverage:'+vid)
    scan_valid=False
    if coverage:
        try:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(coverage['checked_at'])).total_seconds()/3600
            scan_valid=(0<=age<=prefs['stale_hours'] and coverage.get('country')==prefs['country'] and coverage.get('marketplace')==prefs['ebay_marketplace'])
        except (ValueError,KeyError,TypeError): pass
    psa_summary='PSA 10 availability could not be checked.'
    if any(l['assessment']['eligible_for_target'] for l in reviewed):
        psa_summary='Reviewed PSA 10 offer available within your preferences and budget.'
    elif reviewed and all(not l['assessment']['within_budget'] for l in reviewed):
        psa_summary='Recorded PSA 10 offers exceed the remaining budget, or budget costs are incomplete.'
    elif psa: psa_summary='PSA 10 candidates exist; identity, costs, delivery or freshness still need review.'
    elif scan_valid: psa_summary='No PSA 10 listing found among the records from this bounded eBay scan; other sources are not fully scanned.'
    return {'listings':listings,'markets':markets,'market':markets[PSA10],'best_by_condition':best,
            'psa10_summary':psa_summary,'scan_coverage':coverage,'scan_current':scan_valid,
            'ranking_method':'PSA 10 first by default; enabled alternatives follow your ordered preference list. Within each bucket compare reviewed fixed-price delivered totals, evidence quality and target/budget fit. Auction bids and incomplete totals are separate.',
            'watch':watch,'copies':[c for c in copies if c['variant_id']==vid]}


def rank_deals(deals,prefs):
    unique={}
    for d in deals:
        l=d['listing']; cert=l.get('cross_post_group')
        key=(d['card']['id'],l['condition_key'],cert or l['id'])
        total=l['assessment']['cost']['total']
        score=(total is None,total if total is not None else float('inf'))
        if key not in unique or score<unique[key][0]: unique[key]=(score,d)
    def sort(d):
        l=d['listing']; a=l['assessment']; condition=l['condition_rank']
        price=(a['label']!='Good buying opportunity',-a['market']['count'],-(a['discount_pct'] if a['discount_pct'] is not None else -1000))
        safety=(not a['eligible_for_target'],not a['within_budget'])
        return safety+((condition,)+price if prefs.get('buying_priority','psa_first')=='psa_first' else price+(condition,))+(-d['priority'],a['cost']['total'] or float('inf'))
    return sorted([x[1] for x in unique.values()],key=sort)
