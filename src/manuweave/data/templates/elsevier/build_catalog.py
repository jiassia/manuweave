"""Rebuild detailed profiles from reviewed JSON facts without template sources."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build():
    for family in ("elsevier", "revtex"):
        directory = ROOT / family
        data = json.loads((directory / "extracted-layouts.json").read_text(encoding="utf-8"))
        for profile in data["profiles"]:
            target = directory / "profiles" / (profile["id"] + ".json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
