"""Transparent, conservative price attractiveness; not an investment-return model."""
from datetime import datetime, timezone, date
import math
import statistics
from .conditions import condition_key, condition_label, condition_known, is_psa10


def age_days(value, today=None):
    # Sale dates are calendar dates validated against the installation's local
    # day. Using UTC here incorrectly rejects today's sales near local midnight.
    today = today or date.today()
    try:
        return (today - date.fromisoformat(value[:10])).days
    except (ValueError, TypeError):
        return 10**6


def convert(value, src, dst, fx):
    if value is None:
        return None
    if not math.isfinite(float(value)) or float(value)<0:
        return None
    if src == dst:
        return float(value)
    if not fx or not 0 <= age_days(fx.get("date", "")) <= 7:
        return None
    rates = fx.get("rates", {})
    if not rates.get(src) or not rates.get(dst):
        return None
    result = float(value) / rates[src] * rates[dst]
    return result if math.isfinite(result) else None


def acquisition(listing, prefs, fx):
    parts = {k: listing.get(k) for k in ["price", "shipping", "fees", "import_cost"]}
    missing = [k for k,v in parts.items() if v is None]
    if listing.get("delivery_eligible") is False:
        missing += ["delivery unavailable to your country"]
    elif "delivery_eligible" in listing and listing["delivery_eligible"] is None:
        missing += ["delivery eligibility"]
    if listing.get("destination_country") != prefs["country"]:
        missing += ["destination-specific costs"]
    if listing.get("listing_type")=="auction":
        missing += ["final auction price"]
    lower = sum(float(v) for v in parts.values() if v is not None)
    amount = convert(lower, listing["currency"], prefs["currency"], fx)
    if amount is None:
        missing += ["current exchange rate"]
    return {"components": parts, "original_currency": listing["currency"], "currency": prefs["currency"],
            "lower_bound": round(amount,2) if amount is not None else None,
            "total": round(amount,2) if amount is not None and not missing else None,
            "unknown": missing, "fx": fx if listing["currency"] != prefs["currency"] else None}


def quantile(values, q):
    ordered = sorted(values, key=lambda x: x[0])
    cut = q * sum(w for _,w in ordered)
    cumulative = 0
    for val, weight in ordered:
        cumulative += weight
        if cumulative >= cut:
            return val
    return ordered[-1][0]


def valuation(variant_id, sales, prefs, fx, today=None, condition=None):
    today = today or date.today()
    wanted=condition or {"grader":"PSA","grade":10}
    bucket=condition_key(wanted)
    eligible, excluded, seen = [], [], set()
    for sale in sales:
        if sale["variant_id"] != variant_id:
            continue
        reason = None
        age = age_days(sale.get("sold_date", ""), today)
        if not sale.get("completed"):
            reason = "Not a confirmed completed sale"
        elif not sale.get("price_disclosed") or sale.get("item_price") is None:
            reason = "Actual transaction price undisclosed"
        elif not sale.get("exact_variant_confirmed"):
            reason = "Exact variant evidence unconfirmed"
        elif condition_key(sale)!=bucket:
            reason = "Different condition, grading company, grade, designation or scale"
        elif not condition_known(sale) or not condition_known(wanted):
            reason = "Condition or grade identity is unresolved"
        elif not is_psa10(sale) and not sale.get("condition_confirmed"):
            reason = "Alternative condition or grade evidence unconfirmed"
        elif age < 0 or age > prefs["lookback_days"]:
            reason = "Outside the eligible sale-date window"
        elif sale.get("transaction_key", sale["id"]) in seen or (sale.get("cert") and (sale.get("grader","PSA"),sale["cert"],sale.get("sold_date")) in seen):
            reason = "Duplicate transaction"
        amount = convert(sale.get("item_price"), sale["currency"], prefs["currency"], fx)
        if not reason and (amount is None or amount <= 0):
            reason = "No usable price or fresh exchange rate"
        if reason:
            excluded.append({**sale, "excluded_reason": reason})
            continue
        seen.add(sale.get("transaction_key",sale["id"]))
        if sale.get("cert"):
            seen.add((sale.get("grader","PSA"),sale["cert"],sale.get("sold_date")))
        eligible.append({**sale, "converted_price": round(amount, 4), "weight": 2 ** (-age / prefs["half_life_days"])})
    # Log-MAD wins over a mean for skewed, illiquid market observations.
    if len(eligible) >= 5:
        logs = [math.log(x["converted_price"]) for x in eligible]
        med = statistics.median(logs)
        mad = statistics.median(abs(x-med) for x in logs)
        limit = max(math.log(1.75), 3 * 1.4826 * mad)
        keep = []
        for sale in eligible:
            if abs(math.log(sale["converted_price"])-med) > limit:
                excluded.append({**sale, "excluded_reason": "Log-MAD outlier filter (minimum 1.75× band)"})
            else:
                keep.append(sale)
        eligible = keep
    n = len(eligible)
    weighted = [(s["converted_price"], s["weight"]) for s in eligible]
    effective = (sum(w for _,w in weighted)**2 / sum(w*w for _,w in weighted)) if n else 0
    adequate = n >= prefs["min_sales"] and effective >= 3
    confidence = "high" if adequate and n >= 10 and effective >= 7 else "medium" if adequate else "low" if n else "none"
    reference = quantile(weighted, 0.5) if adequate else None
    return {"count": n, "effective_count": round(effective, 2), "confidence": confidence,
            "reference": round(reference,2) if reference else None,
            "range": [round(quantile(weighted,.25),2), round(quantile(weighted,.75),2)] if adequate else None,
            "included": eligible, "excluded": excluded, "currency": prefs["currency"], "fx": fx,
            "condition_key":bucket,"condition_label":condition_label(wanted),
            "method": f"Recency-weighted median of exact {condition_label(wanted)} item-only completed sales; {prefs['lookback_days']}-day window, {prefs['half_life_days']}-day half-life; log-MAD outlier filter when n≥5. Range = weighted 25th–75th percentiles, not a confidence interval. All FX conversions use the displayed current reference rate, not historical sale-day FX.",
            "reason": "Comparable completed-sale evidence meets the configured minimum." if adequate else f"Need {prefs['min_sales']} eligible sales and an effective sample of 3; currently {n} sales, effective {effective:.1f}."}


def budget_state(copies, prefs, fx):
    spent = 0
    unknown = 0
    for copy in copies:
        components = [copy.get(k) for k in ["purchase_price", "shipping", "fees", "import_cost"]]
        val = convert(sum(float(x) for x in components if x is not None), copy["currency"], prefs["currency"], fx)
        if any(x is None for x in components) or val is None:
            unknown += 1
        spent += val or 0
    remaining = None if prefs["budget"] is None or unknown else max(0, prefs["budget"]-spent)
    return {"limit": prefs["budget"], "committed_lower_bound": round(spent,2), "unknown_cost_copies": unknown,
            "remaining": round(remaining,2) if remaining is not None else None, "currency": prefs["currency"]}


def assess(listing, match, market, prefs, fx, budget):
    cost = acquisition(listing, prefs, fx)
    issues = []
    stale = age_days(listing.get("checked_at", "")) >= 10**6
    try:
        checked = datetime.fromisoformat(listing["checked_at"].replace("Z", "+00:00"))
        hours = (datetime.now(timezone.utc)-checked).total_seconds()/3600
        stale = hours > prefs["stale_hours"] or hours < -0.05
    except (ValueError, KeyError, TypeError):
        stale = True
    if match.get("status") != "verified":
        issues.append("Exact item has not passed the required identity, photo and condition/grade review")
    if not condition_known(listing):
        issues.append("Condition / grade identity is unresolved")
    if match.get("condition_key") and match["condition_key"]!=condition_key(listing):
        issues.append("Condition changed after review")
    minimum=prefs.get("min_seller_feedback")
    if minimum is not None and (listing.get("seller_feedback") is None or float(listing["seller_feedback"])<minimum):
        issues.append("Seller feedback is below your minimum or unavailable")
    if prefs.get("seller_countries") and listing.get("seller_country") not in prefs["seller_countries"]:
        issues.append("Seller location is outside your allowed countries or unknown")
    ended=False
    if listing.get("end_at"):
        try:
            ended=datetime.fromisoformat(listing["end_at"].replace("Z","+00:00"))<=datetime.now(timezone.utc)
        except (ValueError,TypeError):
            ended=True
    if listing.get("status") != "active" or stale or ended:
        issues.append("Listing is unavailable, ended, or stale")
    if listing["listing_type"] == "auction":
        issues.append("Current auction bid is not a final acquisition price")
    if cost["total"] is None:
        issues.append("Total cost is incomplete: " + ", ".join(cost["unknown"]))
    if listing.get("price", 0) <= 0:
        issues.append("Non-positive asking price requires review")
    price_issues = list(issues)
    if market.get("condition_key") and market["condition_key"]!=condition_key(listing):
        price_issues.append("Market reference is for a different condition bucket")
    if market["reference"] is None:
        price_issues.append(market["reason"])
    discount = None
    label = "Insufficient data"
    if not price_issues:
        discount = 100*(1-cost["total"]/market["reference"])
        label = "Good buying opportunity" if discount >= prefs["bargain_pct"] else "Expensive" if discount <= -prefs["expensive_pct"] else "Fair price"
    within_budget = budget["limit"] is None or (budget["remaining"] is not None and cost["total"] is not None and cost["total"] <= budget["remaining"])
    explanation = "; ".join(price_issues) if price_issues else f"Estimated delivered cost is {abs(discount):.1f}% {'below' if discount >= 0 else 'above'} the recency-weighted median of {market['count']} exact-variant {condition_label(listing)} completed sales. Reference is historical item-only price, not historical delivered cost."
    if not within_budget:
        explanation += " Outside the remaining budget, or recorded collection costs are incomplete."
    return {"label": label, "discount_pct": round(discount,2) if discount is not None else None,
            "cost": cost, "match_confidence": match.get("confidence", "unverified"),
            "condition_key":condition_key(listing), "condition_label":condition_label(listing),
            "condition_confidence": match.get("condition_confidence", "owner-reviewed" if match.get("status")=="verified" else "unknown"),
            "price_confidence": market["confidence"], "market": market, "within_budget": within_budget,
            "eligible_for_target": not issues and within_budget, "explanation": explanation}
