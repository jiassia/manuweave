"""Optional developer matrix using installed local tools; not a normal Skill gate."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from manuweave.matrix import run_matrix  # noqa: E402


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Optional development checks with installed local Word/LaTeX tools.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--names", nargs="+")
    args = parser.parse_args()
    report = run_matrix(args.output, args.names)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
