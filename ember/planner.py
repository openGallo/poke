"""Evidence-limited completion estimates and same-seller purchase grouping."""
from collections import defaultdict
from .catalogue import in_scope
from .conditions import condition_key, preference_keys, is_psa10
from .pricing import valuation, convert, budget_state


def completion_estimate(db, preferences):
    copies = db.records("copies")
    owned = {c["variant_id"] for c in copies if c["status"] == "Owned" and is_psa10(c)}
    sales = db.records("sales")
    fx = db.get("fx")
    known, missing = [], 0
    for variant in db.records("variants"):
        if not in_scope(variant, preferences) or variant["id"] in owned:
            continue
        missing += 1
        estimate = valuation(variant["id"], sales, preferences, fx)
        if estimate.get("reference") is not None:
            known.append(estimate)
    return {"missing_psa10_variants": missing, "priced_variants": len(known),
            "unpriced_variants": missing - len(known), "currency": preferences["currency"],
            "known_item_estimate": round(sum(x["reference"] for x in known), 2) if known else None,
            "known_item_range": [round(sum(x["range"][i] for x in known),2) for i in (0,1)] if known else None,
            "complete": bool(missing and len(known) == missing),
            "basis": "PSA 10 item-only references from eligible completed sales; shipping, fees and imports are additional. Unpriced cards have no invented value."}


def seller_groups(deals, preferences, fx, copies=()):
    budget=budget_state(copies,preferences,fx)
    groups = defaultdict(dict)
    for deal in deals:
        listing = deal["listing"]
        assessment = listing["assessment"]
        if not assessment.get("eligible_for_target") or not assessment.get("needed_for_collection") or not assessment.get("preference_eligible"):
            continue
        seller = listing.get("seller", "").strip()
        if not seller:
            continue
        key = (listing.get("source", "Manual"), seller)
        vid = deal["card"]["id"]
        current = groups[key].get(vid)
        if current is None or (listing["condition_rank"], assessment["cost"]["total"]) < (current["listing"]["condition_rank"], current["listing"]["assessment"]["cost"]["total"]):
            groups[key][vid] = deal
    output = []
    for (source, seller), variants in groups.items():
        if len(variants) < 2:
            continue
        items = list(variants.values())
        total = round(sum(d["listing"]["assessment"]["cost"]["total"] for d in items), 2)
        shipping = sum(convert(d["listing"]["shipping"], d["listing"]["currency"], preferences["currency"], fx) for d in items)
        output.append({"source": source, "seller": seller, "variants": len(items),
            "individual_total": total, "separate_shipping": round(shipping, 2),
            "currency": preferences["currency"], "within_budget": preferences.get("budget") is None or (budget["remaining"] is not None and total<=budget["remaining"]),
            "items": [{"title": d["listing"]["title"], "url": d["listing"]["url"], "variant_id": d["card"]["id"]} for d in items],
            "message": "Ask this seller for combined shipping. No saving is assumed; import charges and fees may also change."})
    return sorted(output, key=lambda g: (-g["variants"], g["individual_total"]))
