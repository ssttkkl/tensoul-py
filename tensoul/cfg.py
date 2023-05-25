import json
from pathlib import Path

with open(Path(__file__).parent / "cfg.json", "r", encoding="utf-8") as f:
    cfg = json.load(f)

__all__ = ("cfg",)
