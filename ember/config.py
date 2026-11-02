from dataclasses import dataclass
from pathlib import Path
import json
import os
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

@dataclass(frozen=True)
class Config:
    data_dir: Path
    password_hash: str
    encryption_key: str
    public_url: str = "http://127.0.0.1:8000"
    scheduler: bool = True
    tick_seconds: float = 60
    monitor_token: str = ""
    testing: bool = False
    desktop: bool = False
    setup_required: bool = False

    def __post_init__(self):
        p = urlsplit(self.public_url)
        if p.scheme not in {"http", "https"} or not p.hostname or p.path not in {"", "/"}:
            raise ValueError("PUBLIC_URL must be an origin, without a path.")
        if p.username or p.password or p.query or p.fragment:
            raise ValueError("PUBLIC_URL may not contain credentials, query or fragment.")
        if p.scheme != "https" and p.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            raise ValueError("Non-local deployments require HTTPS.")
        if not self.password_hash or not self.encryption_key:
            raise ValueError("Run `python -m ember setup` before starting Ember.")
        if not self.testing and self.tick_seconds < 60:
            raise ValueError("Production scheduler wake interval must be at least 60 seconds.")

    @property
    def secure(self) -> bool:
        return self.public_url.startswith("https:")

    @property
    def origin(self) -> str:
        return self.public_url.rstrip("/")

    @classmethod
    def load(cls, data_dir: Path | None = None):
        path = Path(data_dir or os.getenv("EMBER_DATA_DIR", "runtime")).resolve()
        f = path / "config.json"
        stored = json.loads(f.read_text()) if f.exists() else {}
        return cls(data_dir=path,
                   password_hash=os.getenv("EMBER_PASSWORD_HASH", stored.get("password_hash", "")),
                   encryption_key=os.getenv("EMBER_ENCRYPTION_KEY", stored.get("encryption_key", "")),
                   public_url=os.getenv("EMBER_PUBLIC_URL", stored.get("public_url", "http://127.0.0.1:8000")),
                   monitor_token=os.getenv("EMBER_MONITOR_TOKEN", stored.get("monitor_token", "")),
                   scheduler=os.getenv("EMBER_SCHEDULER", "true").lower() == "true",
                   setup_required=stored.get("setup_required", False))
