"""Explicit condition identities; seller vocabulary is not a grading equivalence.

Every raw price bucket includes the source's condition scale. CGC scale eras and
BGS/CGC designations remain distinct. Nothing here authenticates a physical card.
"""
from __future__ import annotations
import re
import unicodedata

RAW_CONDITIONS = ["Mint", "Near Mint", "Near Mint or Better", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged", "Excellent", "Good", "Played", "Poor", "Unknown"]
CONDITION_SCALES = ["seller", "ebay", "tcgplayer", "cardmarket"]
GRADERS = ["PSA", "BGS", "CGC", "RAW", "UNKNOWN"]
PSA10 = "graded:PSA:10:Gem Mint:current"


def _norm(s):
    return " ".join(unicodedata.normalize("NFKC", str(s or "")).casefold().split())


def source_scale(source):
    return {"ebay":"ebay", "cardmarket":"cardmarket", "tcgplayer":"tcgplayer"}.get(_norm(source), "seller")


def normalize_raw(wording, source="Manual"):
    """Only explicit descriptions map. 'Used', 'New', ranges and marketing stay unknown."""
    text=_norm(wording)
    scale=source_scale(source)
    common={"mint":"Mint", "m":"Mint", "near mint":"Near Mint", "nm":"Near Mint",
            "lightly played":"Lightly Played", "lp":"Lightly Played",
            "moderately played":"Moderately Played", "mp":"Moderately Played",
            "heavily played":"Heavily Played", "hp":"Heavily Played",
            "damaged":"Damaged", "dmg":"Damaged"}
    if scale=="cardmarket":
        mapping={"mint":"Mint","mt":"Mint","near mint":"Near Mint","nm":"Near Mint",
                 "excellent":"Excellent","ex":"Excellent","good":"Good","gd":"Good",
                 "light played":"Lightly Played","lp":"Lightly Played",
                 "played":"Played","pl":"Played","poor":"Poor","po":"Poor"}
    elif scale=="ebay":
        mapping={**common, "near mint or better":"Near Mint or Better",
                 "lightly played (excellent)":"Lightly Played",
                 "moderately played (very good)":"Moderately Played",
                 "heavily played (poor)":"Heavily Played"}
    else:
        mapping=common
    category=mapping.get(text,"Unknown")
    return {"raw_condition":category,"condition_scale":scale,"condition_original":str(wording or ""),
            "condition_mapping":"Exact source vocabulary; scales are not interchangeable" if category!="Unknown" else "Unmapped or ambiguous description; manual condition review needed"}


def condition_data(item):
    """Read v2 PSA records without destructive rewrites. Never infer raw from a blank grader."""
    g=str(item.get("grader","PSA") or "UNKNOWN").upper()
    grade=item.get("grade",10 if g=="PSA" else None)
    try:
        grade=float(grade) if grade is not None else None
    except (ValueError,TypeError):
        grade=None
    designation=item.get("designation","") or ""
    if g=="PSA" and grade==10: designation="Gem Mint"
    elif g=="PSA" and grade==9: designation="Mint"
    elif g=="BGS" and grade==9.5: designation="Gem Mint"
    scale=item.get("grading_scale","current")
    return {"grader":g,"grade":grade,"designation":designation,"grading_scale":scale,
            "raw_condition":item.get("raw_condition","Unknown"),
            "condition_scale":item.get("condition_scale","seller"),
            "condition_original":item.get("condition_original","")}


def condition_key(item):
    c=condition_data(item)
    if c["grader"]=="RAW": return f'raw:{c["condition_scale"]}:{c["raw_condition"]}'
    if c["grader"]=="UNKNOWN" or c["grade"] is None: return "unknown"
    return f'graded:{c["grader"]}:{c["grade"]:g}:{c["designation"]}:{c["grading_scale"]}'


def condition_label(item):
    c=condition_data(item)
    if c["grader"]=="RAW": return f'Raw · {c["raw_condition"]} ({c["condition_scale"]} scale)'
    if c["grader"]=="UNKNOWN" or c["grade"] is None: return "Condition / grade unknown"
    return " ".join(x for x in [c["grader"],f'{c["grade"]:g}',c["designation"],f'({c["grading_scale"]} scale)' if c["grader"]=="CGC" else ""] if x)


def is_psa10(item):
    c=condition_data(item)
    return c["grader"]=="PSA" and c["grade"]==10


def condition_known(item):
    c=condition_data(item)
    if c["grader"]=="RAW": return c["raw_condition"]!="Unknown"
    if c["grader"] not in {"PSA","BGS","CGC"} or c["grade"] is None: return False
    if not 1<=c["grade"]<=10 or c["grade"]*2!=int(c["grade"]*2): return False
    if c["grader"]=="PSA" and c["grade"]==9.5: return False
    if c["grader"]=="CGC" and c["grading_scale"]=="unspecified": return False
    if c["grader"] in {"BGS","CGC"} and c["grade"]==10 and not c["designation"]: return False
    return True


def cert_identity(item, cert=None):
    cert=str(cert if cert is not None else item.get("cert", "")).strip().upper()
    return f'{condition_data(item)["grader"]}:{cert}' if cert else None


def bucket_options():
    out=[]
    def add(c): out.append({"key":condition_key(c),"label":condition_label(c),"fields":condition_data(c)})
    for g in range(10,0,-1): add({"grader":"PSA","grade":g})
    for g in [8.5,7.5,6.5,5.5,4.5,3.5,2.5,1.5]: add({"grader":"PSA","grade":g})
    for d in ["Pristine","Black Label"]: add({"grader":"BGS","grade":10,"designation":d})
    for g in [9.5,9,8.5,8,7.5,7,6.5,6,5.5,5,4.5,4,3.5,3,2.5,2,1.5,1]: add({"grader":"BGS","grade":g})
    for scale in ["current","legacy"]:
        for d in (["Gem Mint","Pristine"] if scale=="current" else ["Perfect","Pristine"]):
            add({"grader":"CGC","grade":10,"designation":d,"grading_scale":scale})
        for g in [9.5,9,8.5,8,7.5,7,6.5,6,5.5,5,4.5,4,3.5,3,2.5,2,1.5,1]: add({"grader":"CGC","grade":g,"grading_scale":scale})
    for scale in CONDITION_SCALES:
        cats=(['Mint','Near Mint','Excellent','Good','Lightly Played','Played','Poor','Unknown'] if scale=='cardmarket' else
              ['Mint','Near Mint','Near Mint or Better','Lightly Played','Moderately Played','Heavily Played','Damaged','Unknown'] if scale=='ebay' else
              ['Mint','Near Mint','Lightly Played','Moderately Played','Heavily Played','Damaged','Unknown'])
        for raw in cats: add({"grader":"RAW","grade":None,"raw_condition":raw,"condition_scale":scale})
    return out


DEFAULT_FALLBACKS=[f"raw:{scale}:{condition}" for scale in CONDITION_SCALES
                   for condition in (["Mint", "Near Mint", "Near Mint or Better"] if scale=="ebay" else ["Mint", "Near Mint"])]


def preference_keys(prefs, watch=None):
    watch=watch or {}
    enabled=watch.get("fallback_enabled")
    if enabled is None: enabled=prefs.get("fallback_enabled",True)
    keys=watch.get("fallback_buckets")
    if keys is None: keys=prefs.get("fallback_buckets",DEFAULT_FALLBACKS)
    return [PSA10]+([k for k in keys if k!=PSA10] if enabled else [])


def allowed_condition(item,prefs,watch=None):
    return condition_known(item) and condition_key(item) in preference_keys(prefs,watch)


def need_listing(vid,item,copies,prefs,watch=None):
    if not allowed_condition(item,prefs,watch): return False
    holdings=[c for c in copies if c["variant_id"]==vid and c["status"] in {"Owned","Ordered"}]
    if any(is_psa10(c) for c in holdings): return False
    if is_psa10(item): return True
    # A fallback is a bridge to PSA 10, not an invitation to buy every lesser grade.
    return not any(allowed_condition(c,prefs,watch) for c in holdings)


def target_for(item,watch,prefs):
    watch=watch or {}; key=condition_key(item)
    return watch.get("targets",{}).get(key,watch.get("target_price") if is_psa10(item) else None)


def condition_rank(item,prefs,watch=None):
    keys=preference_keys(prefs,watch)
    return keys.index(condition_key(item)) if condition_key(item) in keys else len(keys)+1


def infer_condition(title,original="",source="Manual",aspects=None):
    """Seller evidence only, not authenticity. Unspecified CGC eras stay unspecified."""
    a={_norm(k):str(v) for k,v in (aspects or {}).items()}; t=_norm(title)
    gstr=_norm(a.get("professional grader",a.get("grader","")))
    identified=[]
    for g,aliases in {"PSA":["psa","professional sports authenticator"],"BGS":["bgs","beckett"],"CGC":["cgc","certified guaranty company"]}.items():
        if any(re.search(r'(?<!\w)'+re.escape(x)+r'(?!\w)',gstr or t) for x in aliases): identified.append(g)
    raw=normalize_raw(original or a.get("card condition",""),source)
    c={"grader":"UNKNOWN","grade":None,"designation":"","grading_scale":"current",**raw}
    if len(identified)==1:
        g=identified[0]
        grade_word=a.get("grade","")
        gm=re.search(r'(?<!\d)(10|[1-9](?:\.5)?)(?!\d)',grade_word)
        if not gm:
            gm=re.search(r'\b(?:psa|bgs|beckett|cgc)\s*(?:gem\s*mint\s*|gem\s*mt\s*|pristine\s*|perfect\s*|black\s*label\s*|mint\s*|grade[d]?\s*)?(10|[1-9](?:\.5)?)(?!\d)',t)
        c.update(grader=g,grade=float(gm[1]) if gm else None,raw_condition="Unknown")
        if g=="CGC": c['grading_scale']='unspecified'
        text=t+' '+_norm(grade_word)
        for phrase,d in [("black label","Black Label"),("pristine","Pristine"),("perfect","Perfect"),("gem mint","Gem Mint")]:
            if phrase in text and g in {"BGS","CGC"}: c['designation']=d; break
        # Current CGC Gem Mint 10 and legacy Perfect 10 explicitly identify their scales.
        if g=='CGC' and c['grade']==10 and c['designation'] in {'Perfect','Gem Mint'}:
            c['grading_scale']='legacy' if c['designation']=='Perfect' else 'current'
    elif not identified and (raw['raw_condition']!='Unknown' or re.search(r'\b(?:raw|ungraded)\b',t) or _norm(original) in {'used','new','ungraded'}):
        c.update(grader='RAW')
        if not original and not a.get('card condition'):
            # Match specific phrases before generic "Mint". Ranges remain unknown.
            if not re.search(r'\bnm\s*[/\-]\s*(?:m|lp)\b|near mint\s*(?:to|/)\s*mint',t):
                for pattern,word in [(r'\bnear mint\b|\bnm\b','Near Mint'),(r'\blightly played\b|\blp\b','Lightly Played'),(r'\bmoderately played\b|\bmp\b','Moderately Played'),(r'\bheavily played\b|\bhp\b','Heavily Played'),(r'\bdamaged\b','Damaged'),(r'\bmint\b','Mint')]:
                    if re.search(pattern,t): c.update(normalize_raw(word,source)); break
    if c['grader']=='PSA' and c['grade']==10: c['designation']='Gem Mint'
    if c['grader']=='PSA' and c['grade']==9: c['designation']='Mint'
    return c
