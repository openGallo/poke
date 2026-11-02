"""Record real empty-app GET responses for static layout review only.

Not an authenticated browser test, a live backend, or a marketplace fixture.
No production data or provider calls are used. Output stays outside the repo.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from ember.config import Config, ROOT
from ember.main import create_app
from ember.security import PH


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    destination=args.destination.resolve()
    if destination==ROOT.parent or ROOT.parent in destination.parents:
        raise SystemExit("Use a fixture directory outside the source package.")
    assets=destination/"dist";assets.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/"static/index.html",assets/"index.html")
    shutil.copytree(ROOT/"static",assets/"static",dirs_exist_ok=True)
    (destination/".openai").mkdir(exist_ok=True)
    (destination/".openai/hosting.json").write_text(json.dumps({"static":{"directory":"dist"}}))
    with tempfile.TemporaryDirectory(prefix="ember-visual-") as directory:
        password="Synthetic visual test fixture only"
        app=create_app(Config(data_dir=Path(directory),password_hash=PH.hash(password),encryption_key=Fernet.generate_key().decode(),public_url="http://testserver",scheduler=False,testing=True))
        with TestClient(app) as client:
            client.post("/api/login",json={"password":password})
            state=client.get("/api/state").json()
            routes=["/api/bootstrap","/api/state","/api/deals","/api/planner","/api/alerts"]+["/api/cards/"+v["id"] for v in state["variants"]]
            for route in routes:
                response=client.get(route)
                response.raise_for_status()
                file=assets/route.lstrip("/");file.parent.mkdir(parents=True,exist_ok=True)
                file.write_bytes(response.content)
    print("Recorded isolated empty-state GET responses; static layout review only.")


if __name__=="__main__":
    main()
