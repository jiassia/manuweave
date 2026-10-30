"""Atomic state and input identity used by plans and resumable runs."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(path: str | Path) -> str:
    path = Path(path)
    h = hashlib.sha256()
    files = sorted(path.rglob("*")) if path.is_dir() else [path]
    for file in files:
        if file.is_symlink():
            raise ValueError("Symlink input is unsupported")
        if not file.is_file():
            continue
        if path.is_dir():
            h.update(file.relative_to(path).as_posix().encode())
            h.update(b"\0")
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def write_json(path: str | Path, data) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".mw-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
