"""Build a self-contained source Skill archive, excluding environments and caches."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Archive output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    excluded = {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__", "dist", "build",
                "tests", "examples", ".github"}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if any(part in excluded or part.endswith(".egg-info") for part in relative.parts):
                continue
            if relative.as_posix() == "scripts/run_template_matrix.py":
                continue
            if path.is_file() and not path.is_symlink() and path.suffix != ".pyc":
                archive.write(path, "manuweave/" + relative.as_posix())
    print(output)


if __name__ == "__main__":
    main()
