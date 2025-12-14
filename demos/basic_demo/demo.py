"""Backwards-compatible entrypoint that wraps the modular line follower."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from demos.line_follower.run_demo import run_demo

if __name__ == "__main__":
    run_demo()
