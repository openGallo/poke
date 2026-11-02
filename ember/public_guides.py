"""No-key TCGdex marketplace aggregates: context, never sales or listing prices.

Only the fixed documented TCGdex host is fetched. Provider groups, currency,
last-update dates and missing breakdowns are preserved; an English API response
is not evidence that an aggregate represents English copies of one condition.
"""
import hashlib
import json
import math
import time
from urllib.parse import quote

import httpx

from .db import dumps, now
from .models import norm
from .providers import SourceError

CM_FIELDS = {"avg", "low", "trend", "avg1", "avg7", "avg30"}
TCG_FIELDS = {"lowPrice", "midPrice", "highPrice", "marketPrice", "directLowPrice"}
TCG_GROUPS = {"normal", "reverse", "holo", "holofoil", "reverse-holofoil", "1st-edition", "1st-edition-holofoil", "unlimited", "unlimited-holofoil"}
MAX_BYTES = 2_000_000
NOTES = ("Provider aggregate context only: exact raw condition, language, edition, stamp and individual sale records are not resolved. "
         "Lows are guide metrics, not buyable listings. Rolling averages are not individual sales or a reconstructed daily history. "
         "Never used for bargain recommendations or collection valuation.")


def parse_guides(body, variant_id, source_url, observed):
    pricing = body.get('pricing')
    if not isinstance(pricing, dict):
        return []
    rows = []
    for source, currency in [('cardmarket', 'EUR'), ('tcgplayer', 'USD')]:
        group = pricing.get(source)
        if not isinstance(group, dict) or group.get('unit') != currency:
            continue
        fields = []
        if source == 'cardmarket':
            fields = [(key, 'holo group' if key.endswith('-holo') else 'standard group', value)
                      for key, value in group.items() if key in CM_FIELDS or key.removesuffix('-holo') in CM_FIELDS]
        else:
            for treatment, values in group.items():
                if treatment in TCG_GROUPS and isinstance(values, dict):
                    fields += [(treatment + '.' + key, treatment, value) for key, value in values.items() if key in TCG_FIELDS]
        for field, treatment, value in fields:
            if isinstance(value, bool):
                continue
            try:
                amount = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(amount) or not 0 < amount <= 100_000_000:
                continue
            rows.append({'variant_id': variant_id, 'source': 'Cardmarket via TCGdex' if source == 'cardmarket' else 'TCGplayer via TCGdex',
                         'source_url': source_url, 'product_id': str(body['id']), 'product_name': str(body.get('name', ''))[:300],
                         'source_field': field, 'condition_label': f'{source} · {treatment} · {field} · condition/language unresolved',
                         'amount': amount, 'currency': currency, 'observed_at': observed,
                         'provider_updated_at': str(group.get('updated', ''))[:60] or None,
                         'observation_type': 'aggregate_estimate', 'sample_count': None, 'sale_dates': None,
                         'identity_confidence': 'Owner-linked base card; aggregate printing/condition scope not independently verified', 'notes': NOTES})
    return rows


async def refresh_guides(db, variant, payload, client=None):
    if not payload.base_card_confirmed:
        raise SourceError('identity_unconfirmed', 'Confirm the TCGdex base-card mapping. Its aggregate guide cannot establish the exact physical printing or condition.')
    lease = db.lease('tcgdex_guides', 60)
    if not lease:
        raise SourceError('busy', 'A public guide refresh is already running.')
    own = client is None
    client = client or httpx.AsyncClient(timeout=12, follow_redirects=False)
    url = f'https://api.tcgdex.net/v2/{variant["language"]}/cards/{quote(payload.provider_id, safe="")}'
    key = 'tcgdex_guide_cache:' + variant['language'] + ':' + payload.provider_id
    try:
        cached = db.get(key)
        cache_hit = bool(cached and time.time() - cached['epoch'] < 86400)
        if cache_hit:
            body = cached['body']; observed = cached['observed_at']
        else:
            last = db.get('tcgdex_guide_last_request', 0)
            if time.time() - last < 2:
                raise SourceError('rate_limited', 'Wait at least two seconds between public guide requests.')
            db.put('tcgdex_guide_last_request', time.time())
            try:
                async with client.stream('GET', url) as response:
                    if response.status_code != 200:
                        raise SourceError('access_error', f'TCGdex guide returned HTTP {response.status_code}. Existing observations are preserved, not refreshed.')
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_BYTES:
                            raise SourceError('provider_error', 'TCGdex response exceeded the safe size limit. No values saved.')
                    body = json.loads(content)
            except (httpx.HTTPError, ValueError, TypeError):
                raise SourceError('connection_error', 'Public guide unavailable or malformed. No prices, transactions or scan coverage were invented.') from None
            observed = now()
        if not isinstance(body, dict) or str(body.get('id')) != payload.provider_id or norm(str(body.get('name', ''))) != norm(variant['name']):
            raise SourceError('identity_mismatch', 'Provider card ID/name does not match the requested base card. No guide saved.')
        local = str(body.get('localId', '')).lstrip('0') or '0'
        expected = variant['number'].split('/')[0].lstrip('0') or '0'
        if local != expected or not isinstance(body.get('set'), dict) or body['set'].get('id') != variant['set_code']:
            raise SourceError('identity_mismatch', 'Provider set or card number conflicts with the selected card. No guide saved.')
        if not cache_hit:
            body = {k: v for k, v in body.items() if k in {'id', 'name', 'localId', 'set', 'pricing'}}
            db.put(key, {'body': body, 'observed_at': observed, 'epoch': time.time()})
        observations = parse_guides(body, variant['id'], url, observed)
        with db.connect() as connection:
            for item in observations:
                ident = hashlib.sha256(dumps([variant['id'], item['source'], item['source_field'], observed]).encode()).hexdigest()
                connection.execute('INSERT OR IGNORE INTO aggregates VALUES(?,?,?)', (ident, variant['id'], dumps(item)))
        status = {'status': 'connected' if observations else 'no_guide_data', 'checked_at': now(), 'observed_at': observed,
                  'message': f'{len(observations)} public aggregate metrics available for this request. Not a listing scan or completed-sales feed.'}
        db.put('tcgdex_guides_status', status)
        return {'observations': observations, 'cached': cache_hit, **status}
    except SourceError as error:
        db.put('tcgdex_guides_status', {'status': error.status, 'checked_at': now(), 'message': error.message})
        raise
    finally:
        db.release('tcgdex_guides', lease)
        if own:
            await client.aclose()
