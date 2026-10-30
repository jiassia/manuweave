"""Run from a skill checkout without relying on the caller's current directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from manuweave.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
