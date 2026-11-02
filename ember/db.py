"""SQLite WAL storage; explicit transactions, non-destructive migrations, no runtime data in Git."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import time
import uuid
from .config import ROOT


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class DB:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
            for migration in sorted((ROOT / "migrations").glob("*.sql")):
                if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (migration.name,)).fetchone():
                    # Each migration is idempotent; record only after successful execution.
                    conn.executescript(migration.read_text())
                    conn.execute("INSERT INTO schema_migrations VALUES(?,?)", (migration.name, now()))
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, key, default=None):
        with self.connect() as c:
            row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        with self.connect() as c:
            c.execute("INSERT INTO kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, dumps(value)))

    def activity(self, message):
        with self.connect() as c:
            c.execute("INSERT INTO activity(time,message) VALUES(?,?)", (now(), message))
            c.execute("DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 500)")

    def rows(self, query, params=()):
        with self.connect() as c:
            return [dict(r) for r in c.execute(query, params).fetchall()]

    def records(self, table):
        if table not in {"variants", "copies", "watchlist", "listings", "sales", "scan_log"}:
            raise ValueError("Invalid record table")
        return [json.loads(r["data"]) for r in self.rows(f"SELECT data FROM {table}")]

    def lease(self, key, ttl=300):
        owner = uuid.uuid4().hex
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("DELETE FROM locks WHERE expires < ?", (time.time(),))
            try:
                c.execute("INSERT INTO locks VALUES(?,?,?)", (key, owner, time.time() + ttl))
            except sqlite3.IntegrityError:
                return None
        return owner

    def release(self, key, owner):
        with self.connect() as c:
            c.execute("DELETE FROM locks WHERE key=? AND owner=?", (key, owner))
