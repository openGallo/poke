"""Conservative candidate screening. No title-only record becomes a verified slab."""
import re
import unicodedata
from .models import LANGUAGES, norm
from .conditions import infer_condition, condition_data, condition_known, condition_key, normalize_raw

NAMES = {"en": ["charmander"], "fr": ["salamèche", "salameche"], "de": ["glumanda"],
         "it": ["charmander"], "es": ["charmander"], "es-mx": ["charmander"], "pt": ["charmander"], "ja": ["ヒトカゲ", "charmander"],
         "ko": ["파이리", "charmander"], "zh-tw": ["小火龍", "charmander"], "zh-cn": ["小火龙", "charmander"],
         "th": ["ฮิโตคาเงะ", "charmander"], "id": ["charmander"]}
LANG_HINTS = {"en": ["english", "anglais", "englisch"], "fr": ["french", "français", "francais", "französisch"],
              "de": ["german", "deutsch", "allemand"], "it": ["italian", "italiano", "italien"],
              "es": ["spanish", "español", "espanol"], "es-mx": ["latin american spanish", "español latinoamericano"], "pt": ["portuguese", "português", "brasileiro"],
              "ja": ["japanese", "japonais", "japanisch", "日本語"], "ko": ["korean", "coréen"],
              "zh-tw": ["traditional chinese"], "zh-cn": ["simplified chinese"], "id": ["indonesian"], "th": ["thai"]}


def number_tokens(title):
    return re.findall(r"(?<![\w])(?:#\s*)?([a-z]{0,5}\d{1,4})(?:\s*/\s*([a-z]{0,5}\d{1,4}))?(?![\w])", norm(title))


def stripped_number(v):
    v = re.sub(r"[^a-z0-9]", "", norm(v))
    return re.sub(r"^([a-z]*)0+(?=\d)", r"\1", v)


def screen(title, variant, aspects=None, condition=None):
    t = norm(title)
    v = variant
    reject, missing, evidence = [], [], []
    declared=condition_data(condition) if condition is not None else infer_condition(title,source="Manual",aspects=aspects)
    # Speculative grade claims are never accepted as an actual grade, even on a raw listing.
    if re.search(r"(?:\bnot\s+(?:a\s+)?(?:psa|bgs|cgc)|\b(?:psa|bgs|cgc)\s*10\s*\?|\b(?:possible|hopefully|likely)\s+(?:psa|bgs|cgc)|\b(?:potential|candidate|contender|worthy)\b)",t):
        reject.append("Negated or speculative grading claim; review the original listing")
    if re.search(r"\b(reprint|proxy|replica|custom)\b",t):
        reject.append("Unofficial reproduction wording")
    if re.search(r"\b(sgc|ace\s+grading|ars\s+\d|hga|gma)\b",t):
        reject.append("Unsupported grading company requires a separately implemented scale")
    observed=infer_condition(title,source="Manual",aspects=aspects)
    companies=set(re.findall(r"\b(psa|bgs|cgc|beckett)\b",t))
    companies={"bgs" if x=="beckett" else x for x in companies}
    if len(companies)>1:
        reject.append("Multiple grading companies: ambiguous listing")
    if declared["grader"]=="RAW" and companies:
        reject.append("Graded title contradicts raw condition")
    if declared["grader"] not in {"RAW","UNKNOWN"}:
        if re.search(r"\b(raw|ungraded|not graded)\b",t):
            reject.append("Raw wording contradicts a graded copy")
        if companies and declared["grader"].lower() not in companies:
            reject.append("Grading company contradicts the recorded condition")
    for company, g in re.findall(r"\b(psa|bgs|beckett|cgc)\s*(?:gem\s*mint\s*|gem\s*mt\s*|pristine\s*|perfect\s*|black\s*label\s*|mint\s*|grade[d]?\s*)?(\d+(?:\.\d+)?)\b",t):
        if declared["grade"] is not None and float(g)!=declared["grade"]:
            reject.append("Numeric grade contradicts the recorded condition")
    if observed.get("grader")!="UNKNOWN" and declared["grader"]!="UNKNOWN":
        if observed["grader"]!=declared["grader"]:
            reject.append("Structured or title grader contradicts recorded condition")
        if observed.get("grade") is not None and declared.get("grade")!=observed["grade"]:
            reject.append("Structured or title grade contradicts recorded condition")
        if observed.get("designation") and declared.get("designation") and observed["designation"]!=declared["designation"]:
            reject.append("Special grade designation contradicts recorded condition")
        if observed.get("grading_scale")!="unspecified" and observed.get("grader")=="CGC" and declared.get("grading_scale")!="unspecified" and observed["grading_scale"]!=declared["grading_scale"]:
            reject.append("CGC grading era contradicts recorded condition")
    if declared.get('grader')=='PSA' and declared.get('grade')==9.5:
        reject.append("PSA 9.5 is not a supported grade")
    for k,value in (aspects or {}).items():
        k=norm(k); value=norm(value)
        if k in {'professional grader','grader'}:
            known=any(alias in value for alias in ['psa','professional sports authenticator','bgs','beckett','cgc','certified guaranty'])
            if not known or declared['grader']=='RAW': reject.append('Structured grader conflicts with recorded condition')
        if k=='grade':
            found_grade=re.search(r'(?<![0-9])(10|[1-9](?:\.5)?)(?![0-9])',value)
            if declared['grader']=='RAW' or not found_grade or (declared['grade'] is not None and float(found_grade[1])!=declared['grade']):
                reject.append('Structured grade contradicts the recorded condition')
    if not condition_known(declared):
        missing.append("Condition, grade, special designation or grading scale requires review")
    if declared["grader"]=="RAW" and condition:
        mapped=normalize_raw(condition.get("condition_original",""),condition.get("source","Manual"))
        if mapped["raw_condition"]!="Unknown" and mapped["raw_condition"]!=declared["raw_condition"]:
            reject.append("Original condition wording contradicts the normalized raw condition")
    if re.search(r"\b(?:lot|bundle|pair|trio|collection\s+of|set\s+of|pick\s+your|choose\s+your|\d+\s*cards|2\s*x|3\s*x)\b", t):
        reject.append("Bundle or selection listing")
    if re.search(r"\b(charizard|charmeleon|dracaufeu|reptincel)\b", t) and not re.search(r"charizard\s*(?:&\s*ho.oh\s*)?(?:ex\s*)?deck", t):
        reject.append("Other Pokémon in the title: ambiguous item")
    if not any(name in t for name in NAMES.get(v["language"], ["charmander"])):
        missing.append("Card name not clearly identified")
    expected = stripped_number(v["number"].split("/")[0])
    tokens = number_tokens(t)
    found = any(stripped_number(a) == expected for a,b in tokens)
    if any(stripped_number(x)!=expected for x in re.findall(r"#\s*([a-z]{0,5}\d{1,4})",t)):
        reject.append("Explicit card number contradicts catalogue")
    if found:
        evidence.append("Card number appears in title")
    else:
        missing.append("Exact card number absent")
    denominators = [b for a,b in tokens if stripped_number(a) == expected and b]
    if "/" in v["number"] and denominators:
        expected_den = stripped_number(v["number"].split("/")[1])
        if any(stripped_number(b) != expected_den for b in denominators):
            reject.append("Card-number denominator contradicts catalogue")
    # An explicit slash number for a different card is a contradiction.
    if any(b and stripped_number(a) != expected for a,b in tokens):
        reject.append("Another card number is explicitly listed")
    languages = [lang for lang, hints in LANG_HINTS.items() if any(re.search(r"(?<!\w)"+re.escape(h)+r"(?!\w)", t) for h in hints)]
    if "es-mx" in languages:
        languages=[lang for lang in languages if lang!="es"]
    elif v["language"]=="es-mx" and languages==["es"]:
        languages=[]  # Generic Spanish does not resolve the regional printing.
    if languages and any(lang != v["language"] for lang in languages):
        reject.append("Language contradicts catalogue")
    if not languages:
        missing.append("Language requires label review")
    if norm(v["set_name"]) not in t and norm(v["set_code"]) not in t:
        missing.append("Set requires label review")
    if re.search(r"\bbase\s+set\s+(?:2|ii)\b", t) and v["set_code"] == "base1":
        reject.append("Base Set 2 contradicts Base Set printing")
    first = bool(re.search(r"\b(?:1st|first|1ère|première)\s*(?:ed(?:ition)?|édition)?\b", t))
    wants_first = "1st" in v["edition"] or "1st" in v["stamp"]
    if first and not wants_first:
        reject.append("First edition contradicts catalogue")
    if wants_first and re.search(r"\bunlimited\b", t):
        reject.append("Unlimited edition contradicts catalogue")
    if wants_first and not first:
        missing.append("First-edition stamp needs review")
    if "shadowless" in t and "shadowless" not in norm(v["print_run"] + " " + v["edition"]):
        reject.append("Shadowless printing contradicts catalogue")
    if "1999-2000" in t and "1999-2000" not in v["print_run"]:
        reject.append("Copyright printing contradicts catalogue")
    if "jumbo" in t and v["size"] != "jumbo":
        reject.append("Jumbo size contradicts catalogue")
    reverse = bool(re.search(r"\breverse\b|\breverse-holo\b", t))
    holo = bool(re.search(r"\bholo(?:graphic)?\b", t))
    non_holo = bool(re.search(r"\bnon[ -]?holo\b", t))
    if reverse and "reverse" not in v["finish"]:
        reject.append("Reverse finish contradicts catalogue")
    if non_holo and v["finish"] != "normal":
        reject.append("Non-holo finish contradicts catalogue")
    if holo and not non_holo and not reverse and v["finish"] == "normal":
        reject.append("Holo finish contradicts catalogue")
    for stamp in ["pokemon center", "pokémon center", "gamestop", "best buy", "eb games", "build a bear", "staff", "prerelease"]:
        def stamp_key(value):
            return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",norm(value)))
        if stamp in t and stamp_key(stamp) not in stamp_key(v["stamp"]):
            reject.append("Stamp contradicts catalogue: " + stamp)
    for pattern in ["master ball", "masterball", "poke ball", "poké ball", "pokeball"]:
        if pattern in t and pattern.replace(" ", "") not in norm(v["finish"] + v["print_run"]).replace(" ", ""):
            reject.append("Foil pattern contradicts catalogue")
    # Distinct foil patterns must not collapse into generic holo/reverse-holo.
    expected_foil = norm(v["finish"] + " " + v["print_run"])
    for pattern, aliases in {
        "cosmos": ["cosmos", "cosmic"],
        "mirage": ["mirage"],
        "cracked ice": ["cracked ice", "cracked-ice"],
        "confetti": ["confetti"],
        "water web": ["water web", "water-web"],
        "smooth cosmos": ["smooth cosmos", "smooth-cosmos"],
        "pixel cosmos": ["pixel cosmos", "pixel-cosmos"],
        "friend ball": ["friend ball", "friendball"],
    }.items():
        if any(re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", t) for a in aliases):
            if not any(a in expected_foil for a in aliases):
                reject.append("Foil pattern contradicts catalogue: " + pattern)
    named = any(x in norm(v["name"]) for x in ["blaine", "auguste", "pyro", "カツラ"])
    if named and not re.search(r"blaine|auguste|pyro|カツラ", t):
        missing.append("Trainer-associated name needs photo verification")
    if bool(re.search(r"blaine|auguste|カツラ", t)) and not named:
        reject.append("Trainer-associated card contradicts catalogue")
    delta = "δ" in v["name"] or "delta" in norm(v["print_run"])
    if ("delta" in t or "δ" in t) and not delta:
        reject.append("Delta Species printing contradicts catalogue")
    # Structured aspects are evidence but never replace photo/cert review.
    for key, value in (aspects or {}).items():
        k = norm(key); value = norm(value)
        if k == "language" and value in {norm(n) for n in LANGUAGES.values()} and value != norm(LANGUAGES[v["language"]]):
            reject.append("Structured language contradicts catalogue")
        if k in {"card number", "card no.", "card no", "collector number"}:
            raw_number = value.replace("#", "").replace(" ", "")
            if re.fullmatch(r"[a-z]{0,5}\d{1,4}(?:/[a-z]{0,5}\d{1,4})?", raw_number):
                parts = raw_number.split("/")
                if stripped_number(parts[0]) != expected:
                    reject.append("Structured card number contradicts catalogue")
                if len(parts) == 2 and "/" in v["number"]:
                    if stripped_number(parts[1]) != stripped_number(v["number"].split("/")[1]):
                        reject.append("Structured card-number denominator contradicts catalogue")
        if k in {"edition", "card edition"}:
            if re.search(r"\b(?:1st|first)\b", value) and not wants_first:
                reject.append("Structured edition contradicts catalogue")
            if value == "unlimited" and wants_first:
                reject.append("Structured edition contradicts catalogue")
        if k in {"card size", "size"} and value in {"jumbo", "oversized", "standard"}:
            if (value in {"jumbo", "oversized"}) != (v["size"] == "jumbo"):
                reject.append("Structured size contradicts catalogue")
    if v["identity_status"] != "documented":
        missing.append("Catalogue printing identity is provisional")
    return {"status": "rejected" if reject else "candidate", "confidence": "rejected" if reject else "unverified",
            "reasons": sorted(set(reject)), "missing": sorted(set(missing)), "evidence": evidence,
            "condition_key":condition_key(declared),"condition_confidence":"rejected" if reject else "seller-asserted" if condition_known(declared) else "unknown"}
