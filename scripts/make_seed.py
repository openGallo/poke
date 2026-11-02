"""Build factual research seed. No prices, listings, sales or collection records."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ember.models import Variant

ROOT=Path(__file__).resolve().parents[1]
B="https://bulbapedia.bulbagarden.net/wiki/"
S={"base":B+"Charmander_(Base_Set_46)", "obs":B+"Charmander_(Obsidian_Flames_26)",
   "151":B+"Charmander_(151_4)", "vivid":B+"Charmander_(Vivid_Voltage_23)",
   "all":B+"Charmander_(TCG)", "gym1":B+"Blaine%27s_Charmander_(Gym_Heroes_61)",
   "gym2":B+"Blaine%27s_Charmander_(Gym_Challenge_60)",
   "tcgdex": "https://github.com/tcgdex/cards-database/blob/master/data/Base/Base%20Set/46.ts"}
rows=[]
def add(set_code, set_name, number, year=None, lang="en", finish="unspecified", edition="unspecified", source="all", **kw):
    local=number.split('/')[0]
    base_id=f"{lang}:{set_code}:{local}"
    image=""
    if lang=="en":
        series = "sv" if set_code.startswith("sv") else "swsh" if set_code.startswith("swsh") else "base" if set_code.startswith("base") else "gym" if set_code.startswith("gym") else ""
        if series:
            image=f"https://assets.tcgdex.net/en/{series}/{set_code}/{local}/high.webp"
    name=kw.pop("name", "ヒトカゲ" if lang=="ja" else "Salamèche" if lang=="fr" else "Glumanda" if lang=="de" else "Charmander")
    row={"base_id":base_id,"name":name,"set_name":set_name,"set_code":set_code,"number":number,"year":year,
         "language":lang,"finish":finish,"edition":edition,"source_url":S.get(source,source),
         "source_checked_at":"2026-10-10", "image_url":image,
         "identity_status":"documented" if finish!="unspecified" and edition!="unspecified" else "provisional", **kw}
    rows.append(Variant.model_validate(row).model_dump())

# English original printings and documented reprints.
for edition,run,stamp in [("unlimited","standard","none"),("1st edition","shadowless","1st-edition"),("unlimited","shadowless","none"),("unlimited","1999-2000-copyright","none")]:
    add("base1","Base Set","46/102",2000 if run=="1999-2000-copyright" else 1999,finish="normal",edition=edition,print_run=run,stamp=stamp,source="tcgdex")
add("base1","Base Set","46/102",2021,finish="normal",edition="standard",size="jumbo",stamp="25th anniversary",release_type="Jumbo",source="base")
for lang in ["fr","de","it"]:
    add("base1","Base Set","46/102",lang=lang,source="tcgdex",notes="Localized identity documented by TCGdex; regional edition and release year still require verification.")
add("base4","Base Set 2","69/130",2000,source="base")
add("base6","Legendary Collection","70/110",2002,source="base")
add("dp7","Stormfront","101/100",2008,source="base")
add("clc","Charizard & Ho-Oh ex Deck","001/034",2023,finish="holo",edition="standard",source="base",release_type="Deck")
add("clc","Charizard & Ho-Oh ex Deck","001/032",2023,lang="ja",finish="holo",edition="standard",source="base",release_type="Deck")
for setcode,setname,number,source in [("gym1","Gym Heroes","61/132","gym1"),("gym2","Gym Challenge","60/132","gym2")]:
    add(setcode,setname,number,2000,source=source,name="Blaine's Charmander")
# Explicit stamped printings from their release documentation.
add("sv03","Obsidian Flames","026/197",2023,finish="mirage-holo",edition="standard",source="obs",print_run="premium-collection")
for stamp in ["none","Pokemon Center"]:
    add("svp","SVP Black Star Promos","044",2023,finish="holo",edition="standard",source="obs",stamp=stamp,release_type="Promo")

add("sv3","Ruler of the Black Flame","012/108",2023,lang="ja",source="obs")
for num in ["051/049","007/049"]:
    add("svg","Venusaur & Charizard & Blastoise Special Deck Set ex",num,2023,lang="ja",source="obs",release_type="Deck")
for stamp,run in [("GameStop","retail"),("EB Games","retail"),("none","costco")]:
    add("sv03.5","151","004/165",2023 if run=="retail" else 2024,finish="cosmos-parallel-holo",edition="standard",stamp=stamp,print_run=run,source="151",identity_status="provisional" if stamp=="GameStop" else "documented",notes="GameStop finish descriptions differ between Bulbapedia and TCGdex; retain as provisional pending release-specific confirmation." if stamp=="GameStop" else "Source describes a Cosmos Parallel Holo release. Do not match an ordinary reverse-holo slab to this record.")
for lang,code,setname,number in [("en","sv03.5","151","004/165"),("en","sv03.5","151","168/165"),("ja","sv2a","Pokémon Card 151","004/165"),("ja","sv2a","Pokémon Card 151","168/165"),("en","sv04.5","Paldean Fates","007/091"),("en","sv04.5","Paldean Fates","109/091"),("ja","sv4a","Shiny Treasure ex","025/190"),("ja","sv4a","Shiny Treasure ex","210/190"),("ja","svjl","Battle Master Deck Terastal Charizard ex","001/021")]:
    if not (lang=="en" and code=="sv03.5" and number=="004/165"):
        add(code,setname,number,2024 if code in ["sv04.5","svjl"] else 2023,lang=lang,source="151")
add("swsh4","Vivid Voltage","023/185",2020,source="vivid")
add("swshp","SWSH Black Star Promos","SWSH092",2021,finish="holo",edition="standard",source="vivid",release_type="Promo")
add("s4","Amazing Volt Tackle","010/100",2020,lang="ja",source="vivid")
add("sp","S-P Promotional cards","112/S-P",2020,lang="ja",finish="normal",edition="standard",stamp="Pokemon Card Gym",source="vivid",release_type="Promo")
add("s8b","VMAX Climax","015/184",2021,lang="ja",source="vivid")
# Checklist-level facts only: printing is intentionally unresolved rather than invented.
for code,name,num,jset,jnum in [
("base5","Team Rocket","50/82","Rocket Gang","unnumbered"),
("ecard1","Expedition Base Set","97/165","Pokémon-e Starter Deck","009/029"),
("ecard1","Expedition Base Set","98/165","Pokémon-e Starter Deck","010/029"),
("ex3","EX Dragon","98/97","Latias ex Half Deck","001/018"),
("ex6","EX FireRed & LeafGreen","113/112","ADV-P Promotional cards","052/ADV-P"),
("ex6","EX FireRed & LeafGreen","57/112","Charizard Starter Deck","009/052"),
("ex6","EX FireRed & LeafGreen","58/112","Charizard Starter Deck","010/052"),
("ex14","EX Crystal Guardians","48/100","Miracle Crystal","011/075"),
("ex14","EX Crystal Guardians","49/100","Earth's Groudon ex Constructed Starter Deck","004/016"),
("pop5","POP Series 5","10/17","PCG-P Promotional cards","132/PCG-P"),
("ex16","EX Power Keepers","48/108","World Champions Pack","006/108"),
("dp3","Secret Wonders","82/132","Shining Darkness","unnumbered"),
("pl4","Arceus","59/99","Advent of Arceus","015/090"),
("bw7","Boundaries Crossed","18/149","Freeze Bolt","010/059"),
("bw11","Legendary Treasures","17/113","EX Battle Boost","009/093"),
("g1","Generations","RC3/RC32","PokéKyun Collection","003/032"),
("xy12","Evolutions","9/108","Expansion Pack 20th Anniversary","009/087"),
("sm3","Burning Shadows","18/147","To Have Seen the Battle Rainbow","009/051"),
("sma","Yellow A Alternate","18a/147","SM-P Promotional cards","060/SM-P"),
("sm7.5","Dragon Majesty","1/70","Dragon Storm","001/053"),
("sma-hidden","Hidden Fates","SV6/SV94","GX Ultra Shiny","166/150"),
("sm9","Team Up","11/181","Tag Bolt","010/095"),
("sm9","Team Up","12/181","Tag Bolt","011/095"),
("sm11.5","Hidden Fates","7/68","Sun & Moon Family Pokémon Card Game","007/051"),
("det1","Detective Pikachu","4/18","Great Detective Pikachu","005/024"),
("swsh10.5","Pokémon GO","008/078","Pokémon GO","008/071"),
("swshp","SWSH Black Star Promos","SWSH232","S-P Promotional cards","289/S-P"),
("svp","SVP Black Star Promos","047","SV-P Promotional cards","060/SV-P"),
]:
    is_delta=(code=="ex14" and num=="49/100") or code=="pop5"
    add(code,name,num,name="Charmander δ" if is_delta else "Charmander")
    import re
    jcode="jp-"+re.sub(r"[^a-z0-9]+","-",jset.lower()).strip("-")
    add(jcode,jset,jnum,lang="ja",name="ヒトカゲ δ" if is_delta else "ヒトカゲ")
for code,name,num in [("mcd21","McDonald's Collection 2021","9/25"),("me02","Phantasmal Flames","011/094"),("me02.5","Ascended Heroes","020/217"),("mep","MEP Black Star Promos","038")]:
    add(code,name,num)
# Standard localized treatments explicitly recorded in TCGdex's source, not inferred translations.
# Source files list the localized names and normal/reverse variants; regional promo cross-products are NOT generated.
for code,setname,number,path in [("sv03","Obsidian Flames","026/197","Obsidian%20Flames/026.ts"),("sv03.5","151","004/165","151/004.ts")]:
    source="https://github.com/tcgdex/cards-database/blob/master/data/Scarlet%20%26%20Violet/"+path
    for language in ["en","fr","de","it","es","pt"]:
        for finish in ["normal","reverse-holo"]:
            add(code,setname,number,2023 if language=="en" else None,lang=language,finish=finish,edition="standard",source=source,
                notes="Localized name and ordinary finish recorded by TCGdex. Language-specific release date not inferred; retailer stamps and special foils have separate identities.",
                image_url=f"https://assets.tcgdex.net/{language}/sv/{code}/{number.split('/')[0]}/high.webp")
assert len({r['id'] for r in rows})==len(rows)
(ROOT/"ember/data/catalogue.json").write_text(json.dumps({"origin":"Rebuilt research seed, not recovered from the original app", "checked_at":"2026-10-10", "complete":False, "sources":S,"variants":rows},ensure_ascii=False,indent=2))
print(f"Seed: {len(rows)} records; {sum(r['identity_status']=='documented' for r in rows)} resolved printings; {len({r['language'] for r in rows})} languages.")
