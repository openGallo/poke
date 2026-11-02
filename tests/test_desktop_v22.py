"""Desktop/onboarding, backup and upgrade checks in isolated temporary storage."""
from dataclasses import replace
import io
import json
import sqlite3
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from ember.catalogue import seed
from ember.config import Config, ROOT
from ember.db import DB, dumps
from ember.desktop import prepare_configuration
from ember.main import create_app
from ember.models import Preferences, Variant
from ember.planner import completion_estimate, seller_groups


def test_gui_setup_preserves_keys_and_survives_restart(config):
    directory=config.data_dir
    initial=prepare_configuration(directory)
    original=(directory/"config.json").read_bytes()
    assert initial.setup_required
    assert prepare_configuration(directory).encryption_key==initial.encryption_key
    assert (directory/"config.json").read_bytes()==original
    app=create_app(replace(initial,public_url="http://testserver",desktop=True,scheduler=False,testing=True))
    password="Synthetic onboarding password 123"
    with TestClient(app) as client:
        assert client.get("/api/bootstrap").json()["setup_required"]
        assert client.get("/api/state").status_code==401
        assert client.post("/api/setup",headers={"Origin":"https://example.com"},json={"password":password,"confirmation":password}).status_code==403
        assert client.post("/api/setup",json={"password":password,"confirmation":"Wrong confirmation"}).status_code==422
        assert client.post("/api/setup",json={"password":password,"confirmation":password}).status_code==200
        assert client.post("/api/setup",json={"password":password,"confirmation":password}).status_code==409
        assert client.post("/api/login",json={"password":password}).status_code==200
        assert client.get("/api/state").json()["preferences"]["languages"]==["en","fr"]
    loaded=Config.load(directory)
    assert loaded.encryption_key==initial.encryption_key and not loaded.setup_required
    with TestClient(create_app(replace(loaded,public_url="http://testserver",scheduler=False))) as client:
        assert client.post("/api/login",json={"password":password}).status_code==200


def test_missing_configuration_never_orphans_existing_database(tmp_path):
    (tmp_path/"ember.sqlite3").write_bytes(b"Synthetic existing database marker")
    with pytest.raises(RuntimeError,match="Restore"):
        prepare_configuration(tmp_path)
    assert not (tmp_path/"config.json").exists()


def test_full_backup_is_private_consistent_and_contains_photos(client,owner,app,config,tmp_path):
    assert client.get("/api/backup").status_code==200  # fixture owner shares this client
    app.state.db.put("synthetic_backup_check",{"owned":True})
    with app.state.db.connect() as conn:
        conn.execute("INSERT INTO images VALUES(?,?,?)",("test-photo",b"synthetic photo bytes","image/png"))
    response=owner.get("/api/backup")
    assert response.headers["cache-control"]=="no-store, private"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        settings=json.loads(archive.read("config.json"))
        assert settings["encryption_key"]==config.encryption_key
        path=tmp_path/"restored.sqlite3"
        path.write_bytes(archive.read("ember.sqlite3"))
        with sqlite3.connect(path) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            assert conn.execute("SELECT content FROM images WHERE key='test-photo'").fetchone()[0]==b"synthetic photo bytes"
            assert json.loads(conn.execute("SELECT value FROM kv WHERE key='synthetic_backup_check'").fetchone()[0])["owned"]


def test_anonymous_backup_and_saved_search_writes_are_rejected(client):
    assert client.get("/api/backup").status_code==401
    assert client.post("/api/saved-searches",json={"name":"test","filters":{}}).status_code==401


def test_saved_filters_persist_and_validate(owner,app,config):
    value={"name":"French promos","filters":{"language":"fr","q":"promo","page":1}}
    result=owner.post("/api/saved-searches",json=value)
    assert result.status_code==200
    assert owner.post("/api/saved-searches",json={"name":"unsafe","filters":{"__proto__":"value"}}).status_code==422
    loaded=create_app(config).state.db.get("saved_searches")
    assert loaded[0]["filters"]==value["filters"]
    assert owner.delete("/api/saved-searches/"+result.json()["id"]).status_code==200
    assert app.state.db.get("saved_searches")==[]


def test_catalogue_upgrade_keeps_referenced_old_ids_and_resolved_data(tmp_path):
    old=json.loads((ROOT/"data/catalogue-2.1.json").read_text())["variants"]
    current=json.loads((ROOT/"data/catalogue.json").read_text())
    provisional=next(v for v in old if v["id"] in current["superseded_provisional_ids"])
    documented=next(v for v in old if v["identity_status"]=="documented")
    db=DB(tmp_path/"test.sqlite3")
    with db.connect() as conn:
        for value in [provisional,documented]:
            conn.execute("INSERT INTO variants VALUES(?,?,?)",(value["id"],value["base_id"],dumps(value)))
        conn.execute("INSERT INTO watchlist VALUES(?,?)",(provisional["id"],dumps({"variant_id":provisional["id"]})))
    seed(db)
    records={v["id"]:v for v in db.records("variants")}
    assert not records[provisional["id"]]["retired"]
    assert records[documented["id"]]==documented
    assert db.records("copies")==[] and db.records("sales")==[]


def test_partial_budget_never_invents_a_collection_total(app):
    result=completion_estimate(app.state.db,Preferences().model_dump())
    assert result["missing_psa10_variants"]>100
    assert result["known_item_estimate"] is None
    assert result["unpriced_variants"]==result["missing_psa10_variants"]


def test_seller_plan_counts_distinct_variants_and_basket_budget():
    prefs=Preferences(budget=15).model_dump()
    def offer(vid, price, ident):
        return {"card":{"id":vid},"listing":{"id":ident,"source":"Synthetic shop","seller":"TEST ONLY","title":"Synthetic "+vid,"url":"https://example.com/"+ident,"condition_rank":0,"shipping":2,"currency":"EUR","assessment":{"eligible_for_target":True,"needed_for_collection":True,"preference_eligible":True,"within_budget":True,"cost":{"total":price}}}}
    rows=[offer("A",10,"1"),offer("A",12,"2"),offer("B",10,"3")]
    groups=seller_groups(rows,prefs,None)
    assert len(groups)==1 and groups[0]["variants"]==2 and groups[0]["individual_total"]==20
    assert not groups[0]["within_budget"] and groups[0]["separate_shipping"]==4
    rows[2]["listing"]["assessment"]["eligible_for_target"]=False
    assert seller_groups(rows,prefs,None)==[]


def test_fresh_preferences_only_recommend_raw_nm_mint_or_psa10():
    p=Preferences()
    assert p.languages==["en","fr"]
    assert p.fallback_buckets and all(key.startswith("raw:") for key in p.fallback_buckets)
    assert all(key.split(":")[-1] in {"Mint","Near Mint","Near Mint or Better"} for key in p.fallback_buckets)


def test_every_original_site_row_has_its_own_active_variant():
    data=json.loads((ROOT/"data/catalogue.json").read_text())
    aliases=data["legacy_aliases"]
    active={v["id"] for v in data["variants"] if not v["retired"]}
    assert len(aliases)==476 and len(set(aliases.values()))==476
    assert set(aliases.values())<=active
    for lang in ["en","ja"]:
        classics=[v for v in data["variants"] if not v["retired"] and v["language"]==lang and v["set_code"] in {"clc","cll"}]
        assert len(classics)==1
    assert not any(v["number"].endswith("/0") for v in data["variants"] if not v["retired"])
    assert not any("/" in v["number"] for v in data["variants"] if not v["retired"] and "black star" in v["set_name"].lower())


def test_imported_hyphenated_stamps_are_not_false_language_or_stamp_conflicts(card):
    from ember.matching import screen
    candidate={**card,"stamp":"pokemon-center","finish":"holo"}
    result=screen("Charmander 46/102 Base Set Unlimited English Pokemon Center holo PSA 10",candidate)
    assert not any("Stamp contradicts" in reason for reason in result.get("reasons",[]))


def test_regional_spanish_is_distinct_but_not_rejected_as_generic_spanish(card):
    from ember.matching import screen
    candidate={**card,"language":"es-mx"}
    result=screen("Charmander 46/102 Base Set Unlimited Latin American Spanish PSA 10",candidate)
    assert not any("Language contradicts" in reason for reason in result.get("reasons",[]))
    other=screen("Charmander 46/102 Base Set Unlimited French PSA 10",candidate)
    assert other["status"]=="rejected"
