"""Backward-compatible entry point for the current offline UI regression suite.
Real browser networking is deliberately NOT claimed by this mode.
"""
from pathlib import Path
import sys
from conditions_ui_checks import run

if __name__ == "__main__":
    run(Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/ember-ui-results"), offline=True)
