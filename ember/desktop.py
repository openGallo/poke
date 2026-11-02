"""Native macOS window around the same authenticated local application.

The server binds a pre-opened loopback socket; no public interface or remote
Python bridge is exposed. Personal files live outside the application bundle.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import fcntl
import json
import logging
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from urllib.request import urlopen, build_opener, ProxyHandler
from cryptography.fernet import Fernet
from .config import Config
from .security import PH


def default_data_dir():
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Ember"
    return Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ember"


def write_configuration(path, values):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(".config-" + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(values, file, indent=2)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_configuration(directory):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    path = directory / "config.json"
    if not path.exists():
        if (directory / "ember.sqlite3").exists():
            raise RuntimeError("Restore your existing config.json before opening this database.")
        write_configuration(path, {"password_hash": PH.hash(secrets.token_urlsafe(48)),
            "encryption_key": Fernet.generate_key().decode(), "monitor_token": secrets.token_urlsafe(48),
            "public_url": "http://127.0.0.1:8000", "setup_required": True})
    return Config.load(directory)


def notification_loop(app, stop):
    db = app.state.db
    notified = set(db.get("desktop_notified_alerts", []))
    while not stop.wait(15):
        preferences = db.get("preferences", {})
        if not preferences.get("notifications", True):
            continue
        for row in db.rows("SELECT id,data FROM alerts WHERE read=0 ORDER BY created_at LIMIT 30"):
            if row["id"] in notified:
                continue
            data = json.loads(row["data"])
            message = str(data.get("message") or data.get("title") or "A new opportunity is in your radar.")[:220]
            try:
                if sys.platform == "darwin":
                    subprocess.run(["/usr/bin/osascript", "-e", 'on run argv\n display notification (item 1 of argv) with title "Ember deal radar"\nend run', message], check=True, timeout=5, capture_output=True)
                notified.add(row["id"])
                db.put("desktop_notified_alerts", sorted(notified)[-2000:])
            except (OSError, subprocess.SubprocessError):
                logging.getLogger("ember.desktop").warning("Desktop notification unavailable; alert retained in the app.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--browser", action="store_true", help="Open the default browser instead of the native window")
    parser.add_argument("--no-open", action="store_true", help="Serve locally for development without opening a window")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    directory = (args.data_dir or Path(os.getenv("EMBER_DATA_DIR", str(default_data_dir())))).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_file = open(directory / "desktop.lock", "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Ember is already running. Open its existing window.")
    logging.basicConfig(filename=directory / "desktop.log", level=logging.INFO)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
    configuration = replace(prepare_configuration(directory), public_url=origin, desktop=True)
    from .main import create_app
    import uvicorn
    app = create_app(configuration)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", log_level="warning", log_config=None, access_log=False, proxy_headers=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    stop = threading.Event()
    thread.start()
    metadata = directory / "desktop-status.json"
    try:
        opener = build_opener(ProxyHandler({}))
        for _ in range(200):
            if not thread.is_alive():
                raise RuntimeError("The local application could not start. See desktop.log.")
            try:
                with opener.open(origin + "/healthz", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("The local application did not become ready.")
        metadata.write_text(json.dumps({"origin": origin, "pid": os.getpid()}))
        metadata.chmod(0o600)
        notifier = threading.Thread(target=notification_loop, args=(app, stop), daemon=True)
        notifier.start()
        if args.no_open or args.browser:
            if args.browser:
                webbrowser.open(origin)
            def shutdown(*_):
                server.should_exit = True
            signal.signal(signal.SIGTERM, shutdown)
            signal.signal(signal.SIGINT, shutdown)
            while thread.is_alive():
                thread.join(0.3)
        else:
            import webview
            webview.settings["ALLOW_DOWNLOADS"] = True
            webview.create_window("Ember — The Charmander Collection", origin, width=1320, height=880, min_size=(760, 600), background_color="#f7f7f2")
            webview.start(debug=args.debug, private_mode=True)
    finally:
        stop.set()
        server.should_exit = True
        thread.join(10)
        sock.close()
        metadata.unlink(missing_ok=True)
        lock_file.close()


if __name__ == "__main__":
    main()
