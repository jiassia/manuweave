"""Rebuild LLNCS profiles from retained structured source facts."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "computer-other/build_profiles.py"))["build"]({"springer"})
