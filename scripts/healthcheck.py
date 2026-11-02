"""Container health probe, preserving the configured host without exposing any secrets."""
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from ember.config import Config
config = Config.load()
r = httpx.get('http://127.0.0.1:8000/healthz', headers={'Host': urlsplit(config.origin).netloc}, timeout=3)
sys.exit(0 if r.status_code == 200 and r.json().get('status') == 'ok' else 1)
