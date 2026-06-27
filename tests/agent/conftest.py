from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = ROOT / "agent" / "src"
AGENT_DIR = ROOT / "agent"

for p in (str(AGENT_SRC), str(AGENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)
