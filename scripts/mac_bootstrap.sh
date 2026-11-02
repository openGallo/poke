#!/bin/bash
# Source-launcher bootstrap. Runtime dependencies are kept outside the app bundle.
set -euo pipefail
SOURCE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUPPORT_DIR="$HOME/Library/Application Support/Ember"
mkdir -p "$SUPPORT_DIR"
chmod 700 "$SUPPORT_DIR"
alert_error() {
  /usr/bin/osascript -e 'on run argv' -e 'display alert "Ember could not start" message (item 1 of argv) as critical' -e 'end run' "$1" || true
}
PYTHON_BIN=""
for candidate in python3.14 python3.13 python3.12 /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3,12))' >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  /usr/bin/osascript -e 'display dialog "Ember needs Python 3.12 or newer for its first setup. Install the macOS package from python.org, then reopen Ember. No terminal commands are needed." buttons {"Cancel", "Open Python downloads"} default button "Open Python downloads"' >/dev/null && /usr/bin/open https://www.python.org/downloads/macos/
  exit 1
fi
PYTHON_ABI="$($PYTHON_BIN -c 'import sys; print(str(sys.version_info.major)+"."+str(sys.version_info.minor))')"
ENV_DIR="$SUPPORT_DIR/python-$PYTHON_ABI"
LOCK_SUM="$(/usr/bin/shasum -a 256 "$SOURCE_ROOT/requirements-desktop.lock" | /usr/bin/awk '{print $1}')"
if [ ! -x "$ENV_DIR/bin/python" ] || [ ! -f "$ENV_DIR/ember-dependencies" ] || [ "$(cat "$ENV_DIR/ember-dependencies" 2>/dev/null || true)" != "$LOCK_SUM" ]; then
  /usr/bin/osascript -e 'display notification "Preparing the app. First setup downloads its Python dependencies and may take a few minutes." with title "Ember"' || true
  if ! "$PYTHON_BIN" -m venv "$ENV_DIR" >>"$SUPPORT_DIR/install.log" 2>&1 || ! "$ENV_DIR/bin/python" -m pip install --disable-pip-version-check -r "$SOURCE_ROOT/requirements-desktop.lock" >>"$SUPPORT_DIR/install.log" 2>&1; then
    alert_error "Dependency setup failed. Check your internet connection. Details are in Library/Application Support/Ember/install.log."
    exit 1
  fi
  printf '%s' "$LOCK_SUM" >"$ENV_DIR/ember-dependencies"
fi
cd "$SOURCE_ROOT"
export EMBER_DATA_DIR="$SUPPORT_DIR"
if [ "${1:-}" = "--build" ]; then
  exec "$ENV_DIR/bin/python" scripts/build_macos.py
fi
exec "$ENV_DIR/bin/python" -m ember.desktop "$@" >>"$SUPPORT_DIR/desktop.log" 2>&1
