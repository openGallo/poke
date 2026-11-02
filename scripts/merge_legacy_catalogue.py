"""Reconcile the recovered Site catalogue with stable 2.1 identities.

Usage: python scripts/merge_legacy_catalogue.py PATH_TO_LEGACY_SOURCE
This reuses dated source evidence; it does not claim a fresh source audit.
"""
from pathlib import Path
from datetime import date
import collections
import hashlib
import json
import re
import shutil
import sys
import unicodedata
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ember.models import Variant

ROOT = Path(__file__).resolve().parents[1]


def simple(value):
    text=unicodedata.normalize("NFKD", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]", "", text)


def signature(v, legacy=False):
    language=v["language"]
    code=v["setId"] if legacy else v["set_code"]
    code={"cll":"clc","jp-s-p-promotional-cards":"sp","base6":"lc","sma-hidden":"sm115"}.get(code,code)
    number=v["cardNumber"] if legacy else v["number"].split("/")[0]
    number=re.sub(r"^0+(?=\d)", "", number)
    edition=v["edition"]
    finish=v["finish"]
    stamp=v.get("stamp") or "none"
    run=v.get("print_run", "standard")
    if legacy and edition in {"shadowless", "1999-2000-copyright"}:
        run=edition; edition="unlimited"
    if legacy and edition=="first-edition-shadowless":
        edition="1st edition";run="shadowless";stamp="1st-edition"
    if edition=="first-edition": edition="1st edition"
    if simple(edition)=="1stedition" and stamp=="none":stamp="1st-edition"
    if stamp=="25th-celebration":stamp="25th anniversary"
    finish={"normal":"non-holo","mirage-holo":"holo","cosmos-parallel-holo":"holo"}.get(finish, finish)
    # Special run identity remains explicit for Base Set; other foils are matched
    # only where there is exactly one legacy candidate with this signature.
    base_run=run if code=="base1" and run in {"shadowless","1999-2000-copyright"} else "standard"
    return tuple(simple(x) for x in [language,code,number,edition,finish,stamp,v.get("size","standard"),base_run])


def merge(source):
    original_path=ROOT/"ember/data/catalogue-2.1.json"
    if not original_path.exists():
        shutil.copyfile(ROOT/"ember/data/catalogue.json", original_path)
    original=json.loads(original_path.read_text())
    legacy=json.loads((source/"data/catalogue.json").read_text())
    old=original["variants"]
    documented=collections.defaultdict(list)
    for v in old:
        if v["identity_status"]=="documented":documented[signature(v)].append(v)
    legacy_signatures=collections.Counter(signature(v,True) for v in legacy)
    output={v["id"]:v for v in old}
    aliases={};manifest={};matched=0
    for row in legacy:
        sig=signature(row,True)
        existing=documented.get(sig, [])
        # The legacy snapshot explicitly leaves EB Games' foil unresolved. Keep
        # its older ID, without creating a second entry for the same stamp.
        conflicting_finish=False
        if not existing and row["finish"]=="unknown":
            candidates=[v for key,items in documented.items() if key[:4]+key[5:]==sig[:4]+sig[5:] for v in items]
            if len(candidates)==1:
                existing=candidates;conflicting_finish=True
        source_url=row["catalogueSource"]
        total=row.get("printedTotal")
        # Promo-series catalogue counts (including zero) are not printed
        # denominators. Retain actual alphanumeric Japanese promo suffixes.
        if total=="0" or ("black star" in row.get("setEnglish",row["set"]).lower() and str(total or "").isdigit()):
            total=None
        num=row["cardNumber"]+("/"+total if total else "")
        image=Path(row["imageUrl"]).name if row.get("imageCached") and row.get("imageUrl") else ""
        notes=row.get("verification", {}).get("notes", [])
        if not isinstance(notes,list):notes=[str(notes)]
        patch={"reference_image": image, "image_note": row.get("imageNote", ""),
            "legacy_id": row["id"], "number_type": row.get("numberType","printed"),
            "evidence_sources": [{"name": s["name"], "url": s["url"]} for s in row.get("sources", [])]}
        if len(existing)==1 and legacy_signatures[sig]==1:
            item={**existing[0], **patch}
            if conflicting_finish:
                item["identity_status"]="provisional"
                item["notes"]="Conflicting foil descriptions in recovered snapshots. Inspect and document the physical printing. "+" ".join(notes)
            matched+=1
        else:
            edition={"first-edition":"1st edition"}.get(row["edition"],row["edition"])
            finish={"non-holo":"normal", "unknown":"unspecified"}.get(row["finish"],row["finish"])
            verified=row.get("identityVerified",False) and finish!="unspecified" and edition!="unspecified"
            release=row.get("releaseDate")
            item={"base_id": row["cardId"], "name": row["name"], "set_name": row["set"], "set_code": row["setId"],
                "number": num, "year": row.get("year"), "language": row["language"], "edition":edition,
                "finish":finish,"stamp":row.get("stamp") or "none", "size":row.get("size","standard"),
                "print_run":row.get("foil") or "standard", "release_type":row["releaseType"].title(),
                "identity_status":"documented" if verified else "provisional", "source_url":source_url,
                "source_checked_at":row.get("lastUpdated","2026-10-10"), "image_url":row.get("imageSourceUrl") or "",
                "provider_id":row.get("sourceCardId", ""), "announced":row.get("releaseStatus")=="announced" or bool(release and release>date.today().isoformat()),
                "notes":" ".join(notes)[:2000], **patch}
        item=Variant.model_validate(item).model_dump()
        output[item["id"]]=item
        aliases[row["id"]]=item["id"]
        if image:
            src=source/"public/cards"/image
            target=ROOT/"ember/static/cards"/image
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(src,target)
            manifest[image]={"sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"source":row.get("imageSourceUrl"),"reference_only":True}
    imported_bases={(r["language"],simple(r["setId"]),simple(r["cardNumber"]).lstrip("0")) for r in legacy}
    imported_named_bases={(r["language"],simple(r["set"]),simple(r["cardNumber"]).lstrip("0")) for r in legacy}
    superseded=[]
    imported_ids=set(aliases.values())
    for v in old:
        if v["id"] in imported_ids:
            continue
        key=(v["language"],simple(v["set_code"]),simple(v["number"].split("/")[0]).lstrip("0"))
        named=(v["language"],simple(v["set_name"]),key[2])
        if v["identity_status"]=="provisional" and (key in imported_bases or named in imported_named_bases):
            output[v["id"]]={**v,"retired":True}
            superseded.append(v["id"])
    data={"version":"2.2-catalogue-1", "origin":"Recovered Ember 2.1 identities plus original Site catalogue",
        "checked_at":"2026-10-10", "complete":False, "sources":original["sources"],
        "superseded_provisional_ids":superseded,"legacy_aliases":aliases,"variants":list(output.values())}
    (ROOT/"ember/data/catalogue.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    (ROOT/"ember/data/reference-assets.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"preserved_old_ids":len(old),"legacy_rows":len(legacy),"matched_existing":matched,
        "active":sum(not v.get("retired") for v in output.values()),"documented":sum(not v.get("retired") and v["identity_status"]=="documented" for v in output.values()),
        "cached_images":len(manifest),"superseded_provisional":len(superseded)}))


if __name__=="__main__":
    merge(Path(sys.argv[1]).resolve())
