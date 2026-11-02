"""Readiness/assets/auth smoke test for an already started isolated desktop process."""
import json
from pathlib import Path
import sys
import time
from urllib.request import ProxyHandler, build_opener

directory=Path(sys.argv[1])
opener=build_opener(ProxyHandler({}))
for _ in range(300):
    status=directory/"desktop-status.json"
    if status.exists():
        origin=json.loads(status.read_text())["origin"]
        try:
            with opener.open(origin+"/healthz",timeout=1) as response:
                assert json.load(response)["status"]=="ok"
            with opener.open(origin+"/api/bootstrap",timeout=1) as response:
                assert json.load(response)["setup_required"]
            with opener.open(origin+"/static/app.js",timeout=1) as response:
                assert b"setupView" in response.read()
            print("Bundled process serves real HTTP, assets and first-run setup.")
            break
        except OSError:
            pass
    time.sleep(.1)
else:
    raise SystemExit("Desktop process did not become healthy.")
