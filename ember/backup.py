"""Consistent owner-requested backup, including the matching encryption configuration."""
import io
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from .db import now


def backup_bytes(config):
    with tempfile.TemporaryDirectory(prefix="ember-backup-") as directory:
        target = Path(directory) / "ember.sqlite3"
        with sqlite3.connect(config.data_dir / "ember.sqlite3") as source, sqlite3.connect(target) as dest:
            source.backup(dest)
            if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed")
        configuration = {
            "password_hash": config.password_hash, "encryption_key": config.encryption_key,
            "monitor_token": config.monitor_token, "public_url": "http://127.0.0.1:8000",
            "setup_required": False,
        }
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(target, "ember.sqlite3")
            archive.writestr("config.json", json.dumps(configuration, indent=2))
            archive.writestr("backup-info.json", json.dumps({"created_at": now(), "includes": ["collection", "photos", "encrypted provider credentials", "matching configuration"], "private": True}))
        return result.getvalue()
