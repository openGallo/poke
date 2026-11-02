"""Local setup, production server and consistent SQLite backups. Never prints credentials."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys

from cryptography.fernet import Fernet
from .config import Config
from .security import PH


def main():
    parser=argparse.ArgumentParser(prog="python -m ember")
    sub=parser.add_subparsers(dest="command",required=True)
    setup=sub.add_parser("setup",help="Initialize owner credentials interactively")
    setup.add_argument("--data-dir",default=os.getenv("EMBER_DATA_DIR","runtime"))
    setup.add_argument("--public-url",default="http://127.0.0.1:8000")
    setup.add_argument("--reset-password",action="store_true",help="Retain encryption key and data, invalidate old sessions")
    serve=sub.add_parser("serve",help="Run one persistent owner-only app process")
    serve.add_argument("--host",default="127.0.0.1")
    serve.add_argument("--port",type=int,default=8000)
    backup=sub.add_parser("backup",help="Consistent private backup using SQLite backup API")
    backup.add_argument("destination",help="Local .sqlite3 path outside the repository")
    args=parser.parse_args()
    if args.command=="setup":
        directory=Path(args.data_dir).resolve(); cfg=directory/"config.json"
        if cfg.exists() and not args.reset_password:
            parser.error("Already configured. Use --reset-password to rotate the owner password without losing data.")
        stored=json.loads(cfg.read_text()) if cfg.exists() else {}
        if (directory/"ember.sqlite3").exists() and not stored.get("encryption_key"):
            parser.error("Existing database without its encryption configuration. Restore your original key before setup; do not orphan credentials.")
        password=getpass.getpass("Choose owner password (at least 12 characters): ")
        confirm=getpass.getpass("Repeat owner password: ")
        if password!=confirm or len(password)<12:
            parser.error("Passwords must match and contain at least 12 characters.")
        data={"password_hash":PH.hash(password),"encryption_key":stored.get("encryption_key") or Fernet.generate_key().decode(),
              "monitor_token":stored.get("monitor_token") or secrets.token_urlsafe(48),
              "public_url":stored.get("public_url",args.public_url) if args.reset_password else args.public_url}
        Config(data_dir=directory,**data)
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        directory.chmod(0o700)
        # O_EXCL prevents accidentally following a pre-existing temporary-file symlink.
        temporary=directory/(".config-"+secrets.token_hex(8))
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w") as file:
            json.dump(data,file,indent=2)
        os.replace(temporary,cfg)
        print("Owner configuration saved privately. No secrets were printed. Run: python -m ember serve")
    elif args.command=="serve":
        config=Config.load()
        if args.host not in {"127.0.0.1","localhost","::1"} and not config.secure:
            parser.error("A non-loopback server requires an HTTPS public origin and a TLS reverse proxy.")
        from .main import create_app
        import uvicorn
        uvicorn.run(create_app(config),host=args.host,port=args.port,workers=1,proxy_headers=False,access_log=False)
    elif args.command=="backup":
        config=Config.load(); target=Path(args.destination).resolve()
        if target.exists():
            parser.error("Backup target already exists; refusing to overwrite it.")
        source=config.data_dir/"ember.sqlite3"
        if not source.exists():
            parser.error("Application database does not exist yet.")
        target.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        try:
            with sqlite3.connect(f"file:{source}?mode=ro",uri=True) as old, sqlite3.connect(target) as new:
                old.backup(new)
                result=new.execute("PRAGMA integrity_check").fetchone()[0]
                if result!="ok":
                    raise RuntimeError("Backup integrity check failed")
        except Exception:
            target.unlink(missing_ok=True);raise
        print("Private backup completed. Store config.json separately and securely; it contains the credential encryption key.")


if __name__=="__main__":
    main()
