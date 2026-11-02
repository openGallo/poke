"""Real desktop-server process test in disposable storage; no native window or provider calls."""
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, HTTPCookieProcessor, Request, build_opener

ROOT=Path(__file__).resolve().parents[1]


def run(destination):
    checks=[]
    with tempfile.TemporaryDirectory(prefix="ember-desktop-process-") as directory:
        storage=Path(directory)
        process=None
        def start():
            child=subprocess.Popen([sys.executable,"-m","ember.desktop","--no-open","--data-dir",directory],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            opener=build_opener(ProxyHandler({}),HTTPCookieProcessor(http.cookiejar.CookieJar()))
            for _ in range(200):
                if child.poll() is not None:
                    raise RuntimeError("Desktop server exited during startup")
                status=storage/"desktop-status.json"
                if status.exists():
                    origin=json.loads(status.read_text())["origin"]
                    try:
                        with opener.open(origin+"/healthz",timeout=1) as response:
                            if json.load(response)["status"]=="ok":
                                return child,opener,origin
                    except OSError:
                        pass
                time.sleep(.05)
            child.terminate();child.wait(10)
            raise RuntimeError("Desktop server did not become ready")
        def request(path,body=None):
            data=json.dumps(body).encode() if body is not None else None
            headers={"Content-Type":"application/json"}
            if csrf:
                headers["X-CSRF-Token"]=csrf
            with opener.open(Request(origin+path,data=data,headers=headers),timeout=10) as response:
                return json.load(response)
        try:
            process,opener,origin=start();csrf=""
            assert request("/api/bootstrap")["setup_required"]
            checks.append("Real loopback desktop process reaches first-run setup")
            password="Synthetic desktop smoke test only 2026"
            assert request("/api/setup",{"password":password,"confirmation":password})["ok"]
            csrf=request("/api/login",{"password":password})["csrf"]
            state=request("/api/state")
            assert state["preferences"]["languages"]==["en","fr"]
            assert state["copies"]==[]
            checks.append("GUI setup endpoint chooses password and owner can sign in over actual HTTP")
            card=next(v for v in state["variants"] if v["language"]=="en" and v["set_code"]=="base1" and v["edition"]=="unlimited" and v["print_run"]=="standard")
            request("/api/copies",{"variant_id":card["id"],"grader":"RAW","grade":None,"raw_condition":"Near Mint","condition_scale":"seller","condition_original":"Near Mint","condition_confirmed":True,"status":"Owned","notes":"SYNTHETIC DESKTOP SMOKE ONLY"})
            state=request("/api/state")
            assert state["completion"]["any_owned"]==1 and state["completion"]["owned"]==0
            checks.append("Raw NM purchase persists without inflating PSA 10 completion")
            process.terminate();process.wait(10)
            process,opener,origin=start();csrf=""
            assert not request("/api/bootstrap")["setup_required"]
            csrf=request("/api/login",{"password":password})["csrf"]
            assert len(request("/api/state")["copies"])==1
            checks.append("Full desktop process restart retains configuration, password and collection")
        finally:
            if process and process.poll() is None:
                process.terminate();process.wait(10)
    report={"scope":"Actual Linux desktop-server subprocesses and HTTP; synthetic temporary records only. Not Cocoa/WebKit or a live provider test.","passed":True,"checks":checks}
    Path(destination).write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))


if __name__=="__main__":
    run(sys.argv[1])
