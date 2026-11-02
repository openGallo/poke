#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
/bin/bash "$PROJECT_DIR/scripts/mac_bootstrap.sh" --build
/usr/bin/open "$PROJECT_DIR/dist"
