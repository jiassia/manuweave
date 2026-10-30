"""Rebuild declarative LLNCS/OUP profiles from structured source facts."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    builder = Path(__file__).resolve().parents[2] / "computer-other/build_profiles.py"
    runpy.run_path(str(builder))["build"]({"springer", "oup"})
