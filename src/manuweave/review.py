"""Bind a host's actual page inspection to immutable rendered artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field

from .io import digest, read_json, write_json
from .models import Contract

VisualStatus = Literal["PASS", "FAIL", "UNKNOWN", "UNVERIFIED", "NOT_APPLICABLE"]


class PageChecks(Contract):
    glyphs: VisualStatus
    overlaps: VisualStatus
    equations: VisualStatus
    tables: VisualStatus
    figures: VisualStatus
    heading_breaks: VisualStatus
    headers_footers: VisualStatus


class PageReview(Contract):
    page: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    checks: PageChecks
    observations: str = Field(min_length=1)


class VisualReview(Contract):
    reviewer: str = Field(min_length=1)
    method: Literal["host_model_image_inspection", "human_image_inspection"]
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    pages: list[PageReview] = Field(min_length=1)


def accept(state_path, review):
    state = read_json(state_path)
    from .pipeline import source_identity
    if source_identity(state["source"]) != state["source_hash"]:
        raise ValueError("Source changed")
    if digest(state["native_root"]) != state["native_hash"]:
        raise ValueError("Native artifact changed")
    directory = Path(state["directory"])
    for name, expected in state["artifacts"].items():
        if digest(directory / name) != expected:
            raise ValueError(f"Saved artifact changed: {name}")
    reviewed = VisualReview.model_validate(review)
    rendered = read_json(directory / "render.json")
    from .pipeline import validate_rendered_artifacts
    validate_rendered_artifacts(rendered)
    if rendered.get("status") != "PASS":
        raise ValueError("A successful real render is required before visual acceptance")
    expected_source = rendered.get("source_sha256", digest(state["native_root"]))
    if reviewed.source_sha256 != expected_source:
        raise ValueError("Visual review source hash mismatch")
    pages = rendered.get("visual", {}).get("pages", [])
    if len(pages) != len(reviewed.pages) or {p["page"] for p in pages} != {p.page for p in reviewed.pages}:
        raise ValueError("Review must cover every rendered page exactly once")
    expected = {p["page"]: p for p in pages}
    values = []
    for page in reviewed.pages:
        saved = expected[page.page]
        if page.sha256 != saved["sha256"] or digest(saved["png"]) != saved["sha256"]:
            raise ValueError("Page image hash mismatch")
        values.extend(page.checks.model_dump().values())
    status = "FAIL" if "FAIL" in values else "PASS" if all(s in {"PASS", "NOT_APPLICABLE"} for s in values) else "UNVERIFIED"
    audit = read_json(directory / "audit.json")
    audit["visual"] = {"status": status, "review": reviewed.model_dump(mode="json"),
                       "geometry": rendered.get("visual", {}).get("geometry", "UNVERIFIED")}
    from .pipeline import final_gate, _record
    final_gate(audit)
    write_json(directory / "visual-review.json", reviewed.model_dump(mode="json"))
    write_json(directory / "audit.json", audit)
    for name in ("visual-review.json", "audit.json"):
        state["artifacts"][name] = digest(directory / name)
    state["result"].update(status=audit["status"], unresolved=audit["unresolved"])
    _record(state, "FINAL_GATE", {"visual_review": status})
    _record(state, "DELIVER", state["result"])
    return state["result"]
