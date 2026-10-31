"""Deterministic plans, bounded repair and durable native-format workflow."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .io import digest, read_json, write_json
from .models import DocumentIR, EditPlan, StyleProfile

STATES = ["INTAKE", "PREFLIGHT", "INVENTORY", "STYLE_RESOLUTION", "ROLE_MAPPING",
          "COMPLETENESS_ANALYSIS", "PLAN", "APPLY", "CONTENT_AUDIT", "STYLE_AUDIT",
          "RENDER", "VISUAL_AUDIT", "REPAIR", "FINAL_GATE", "DELIVER"]


def source_identity(source):
    if Path(source).suffix.lower() == ".docx":
        return digest(source)
    from .latex import _project
    root, main, files = _project(source)
    hashes = {p.relative_to(root).as_posix(): digest(p) for p in files}
    data = {"main": main.relative_to(root).as_posix(), "files": hashes}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def inspect(source):
    source = Path(source).resolve()
    if source.suffix.lower() == ".docx":
        from .word import inspect_docx
        return inspect_docx(source)
    from .latex import inspect_latex
    return inspect_latex(source)


def document_ir(source):
    raw = inspect(source)
    blocks = []
    for block in raw["blocks"] + raw.get("object_blocks", []):
        location = block.get("source", {})
        if isinstance(location, str):
            location = {"file": location}
        blocks.append({"id": block["id"], "role": block.get("role", "unknown"), "text": block.get("text", ""),
                       "source": {"file": location.get("part", location.get("file", str(source))),
                                  "locator": str(location.get("xpath", location.get("line", location)))},
                       "properties": block.get("format", {})})
    return DocumentIR(source=str(Path(source).resolve()), kind=raw["kind"], blocks=blocks,
                      inventory=raw["inventory"]).model_dump(mode="json")


def resolve_profile(preset=None, reference=None):
    if bool(preset) == bool(reference):
        raise ValueError("Choose exactly one preset/profile or reference DOCX")
    if reference:
        if Path(reference).suffix.lower() == ".docx":
            from .word import learn_docx
            profile = learn_docx(reference)
        else:
            from .latex import learn_latex_style
            profile = learn_latex_style(reference)
    else:
        from .presets import load_preset
        profile = load_preset(str(preset))
    return StyleProfile.model_validate(profile).model_dump(mode="json", exclude_none=True)


def plan(source, profile, roles=None):
    source = Path(source).resolve()
    raw = inspect(source)
    known = {b["id"] for b in raw["blocks"]}
    if set(roles or {}) - known:
        raise ValueError("Role map contains unknown source block IDs")
    operations = [{"op": "assign_role", "target": target, "role": role} for target, role in (roles or {}).items()]
    operations.append({"op": "format_document", "target": "document"})
    return EditPlan(source=str(source), source_hash=source_identity(source), profile=profile,
                    operations=operations).model_dump(mode="json", exclude_none=True)


def audit(before, after, profile=None, roles=None):
    if Path(before).suffix.lower() == ".docx":
        from .word import audit_docx
        report = audit_docx(before, after, profile, roles)
    else:
        from .latex import audit_latex
        report = audit_latex(before, after, profile)
    if profile and "template" in profile:
        from .templates import audit_requirements
        report["requirements"] = audit_requirements(after, profile, roles)
    return report


def check_status(report, key):
    value = report.get(key, "UNVERIFIED")
    return value.get("status", "UNVERIFIED") if isinstance(value, dict) else value


def final_gate(report):
    """Use the same complete set of checks before and after page review."""
    keys = ["content", "style", "visual"]
    keys.extend(key for key in ("requirements", "render", "fonts", "rendered_fonts", "field_refresh")
                if key in report)
    checks, unresolved = [], []
    for key in keys:
        status = check_status(report, key)
        checks.append(status)
        if status in {"PASS", "NOT_APPLICABLE"}:
            continue
        value = report.get(key)
        details = []
        if isinstance(value, dict):
            if value.get("reason"):
                details.append(str(value["reason"]))
            if value.get("missing"):
                details.append("Missing fonts: " + ", ".join(value["missing"]))
            for item in value.get("checks", []):
                if item.get("status") in {"PASS", "NOT_APPLICABLE"}:
                    continue
                actual = sorted({entry.get("font", "") for entry in item.get("actual", [])})
                detail = f"{item.get('property', item.get('id', 'check'))}: {item.get('status', 'UNVERIFIED')}"
                if item.get("expected"):
                    detail += f"; expected {item['expected']}"
                if actual:
                    detail += "; observed " + ", ".join(actual)
                if item.get("reason"):
                    detail += "; " + item["reason"]
                details.append(detail)
        unresolved.append(f"{key}: {status}" + ("; " + "; ".join(details) if details else ""))
    geometry = report.get("visual", {}).get("geometry")
    if geometry == "FAIL":
        checks.append("FAIL")
        unresolved.append("visual.geometry: FAIL; Rendered text extends outside the page")
    report["status"] = ("FAIL" if "FAIL" in checks else
                        "PASS" if all(s in {"PASS", "NOT_APPLICABLE"} for s in checks) else "UNVERIFIED")
    report["unresolved"] = unresolved
    return report


def validate_rendered_artifacts(rendered):
    """Reject changed PDFs and page images before reusing a saved result."""
    if rendered.get("pdf") and str(rendered["pdf"]) not in rendered.get("artifact_hashes", {}):
        raise ValueError("Saved PDF identity is unavailable; create a new run")
    for name, expected in rendered.get("artifact_hashes", {}).items():
        path = Path(name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"Rendered artifact changed: {name}")
    # Page identities also bind legacy image-only fixtures without a PDF.
    for page in rendered.get("visual", {}).get("pages", []):
        path = Path(page["png"])
        if not path.is_file() or digest(path) != page["sha256"]:
            raise ValueError(f"Rendered artifact changed: {path}")


def apply(edit_plan, output):
    validated = EditPlan.model_validate(edit_plan)
    source = Path(validated.source)
    if source_identity(source) != validated.source_hash:
        raise ValueError("Source changed since planning; regenerate the plan")
    known = {b["id"] for b in inspect(source)["blocks"]}
    roles = {}
    format_count = 0
    for op in validated.operations:
        if op.op == "assign_role":
            if op.target not in known:
                raise ValueError("Plan targets an unknown block")
            roles[op.target] = op.role
        else:
            format_count += 1
    if format_count != 1:
        raise ValueError("A plan must contain exactly one format_document operation")
    profile = validated.profile.model_dump(mode="json", exclude_none=True)
    if source.suffix.lower() == ".docx":
        from .templates import guard_engine
        guard_engine(profile, "docx")
        from .word import apply_docx
        return apply_docx(source, output, profile, roles)
    if roles:
        raise ValueError("LaTeX role overrides are not yet supported; no edit applied")
    from .latex import apply_latex
    return apply_latex(source, output, profile)


def repair(edit_plan, output, max_rounds=2):
    if not 1 <= max_rounds <= 3:
        raise ValueError("Repair round limit must be 1..3")
    # Reapply the verified source with validated corrected rules. Never remove content.
    result = apply(edit_plan, output)
    result["repair"] = {"rounds": 1, "limit": max_rounds,
                        "strategy": "reapply validated formatting from intact source",
                        "unresolved": [] if check_status(result["audit"], "style") == "PASS" else
                        ["Rules remain unsatisfied; host must revise the profile or role map before another bounded repair."]}
    return result


def _record(state, stage, detail=None):
    state["stage"] = stage
    state["events"].append({"stage": stage, "at": datetime.now(timezone.utc).isoformat(), "detail": detail})
    write_json(state["state_path"], state)


def _artifact(state, name, data):
    target = Path(state["directory"]) / name
    write_json(target, data)
    state["artifacts"][name] = digest(target)
    write_json(state["state_path"], state)


def run(source=None, output=None, profile=None, state_path=None):
    from .completeness import analyze_missing
    from .render import render
    if state_path:
        state = read_json(state_path)
        if Path(state["state_path"]).resolve() != Path(state_path).resolve():
            raise ValueError("State location mismatch")
        if source_identity(state["source"]) != state["source_hash"]:
            raise ValueError("Source changed; resume refused")
        for name, expected in state["artifacts"].items():
            if digest(Path(state["directory"]) / name) != expected:
                raise ValueError(f"Saved artifact changed: {name}")
        if state.get("native_root") and digest(state["native_root"]) != state["native_hash"]:
            raise ValueError("Native output changed since application")
        if "render.json" in state["artifacts"]:
            validate_rendered_artifacts(read_json(Path(state["directory"]) / "render.json"))
        if state.get("finished"):
            return state["result"]
    else:
        source, output = Path(source).resolve(), Path(output).resolve()
        if output.exists():
            raise FileExistsError("Run directory must be new")
        if source.is_dir() and source in output.parents:
            raise ValueError("Run directory must be outside source")
        output.mkdir(parents=True)
        state = {"version": "1.0.0", "state_path": str(output / "state.json"), "directory": str(output),
                 "source": str(source), "source_hash": source_identity(source), "profile": profile,
                 "events": [], "artifacts": {}, "finished": False}
        _record(state, "INTAKE", {"mode": "format_only"})
    directory, source = Path(state["directory"]), Path(state["source"])
    profile = state["profile"]
    try:
        if "plan.json" not in state["artifacts"]:
            _record(state, "PREFLIGHT")
            raw = inspect(source)
            _record(state, "INVENTORY")
            _artifact(state, "ir.json", document_ir(source))
            _record(state, "STYLE_RESOLUTION")
            _artifact(state, "profile.json", profile)
            _record(state, "ROLE_MAPPING")
            _artifact(state, "roles.json", {"roles": {b["id"]: b["role"] for b in raw["blocks"]}})
            _record(state, "COMPLETENESS_ANALYSIS")
            _artifact(state, "missing.json", analyze_missing(raw))
            _record(state, "PLAN")
            _artifact(state, "plan.json", plan(source, profile))
        edit_plan = read_json(directory / "plan.json")
        if "apply.json" not in state["artifacts"]:
            _record(state, "APPLY")
            candidate = directory / ("editable.docx" if source.suffix.lower() == ".docx" else "latex")
            if candidate.exists():
                if source.suffix.lower() == ".docx":
                    native = candidate
                    applied = {"output": str(candidate)}
                else:
                    from .latex import _project
                    root, main, _ = _project(source)
                    applied = {"output": str(candidate), "main": main.relative_to(root).as_posix()}
                    native = candidate / applied["main"]
                recovered = audit(source, native, profile)
                if any(check_status(recovered, key) != "PASS" for key in ("content", "style")):
                    raise ValueError("Interrupted candidate failed revalidation; original retained")
                applied.update(audit=recovered, changes=[{"operation": "recovered_verified_candidate"}])
            else:
                applied = apply(edit_plan, candidate)
            native = candidate / applied["main"] if "main" in applied else candidate
            state["native"] = str(native)
            state["native_hash"] = digest(candidate)
            state["native_root"] = str(candidate)
            _artifact(state, "apply.json", applied)
        if digest(state["native_root"]) != state["native_hash"]:
            raise ValueError("Native output changed since application")
        native = Path(state["native"])
        _record(state, "CONTENT_AUDIT")
        report = audit(source, native, profile)
        if check_status(report, "content") != "PASS":
            raise ValueError("Content failure: candidate quarantined, original retained")
        _record(state, "STYLE_AUDIT")
        from .templates import audit_requirements
        if check_status(report, "style") == "FAIL":
            _record(state, "REPAIR", {"round": 1, "limit": 2})
            fixed = directory / ("repaired.docx" if source.suffix.lower() == ".docx" else "latex-repaired")
            repaired = repair(edit_plan, fixed)
            native = fixed / repaired["main"] if "main" in repaired else fixed
            report = audit(source, native, profile)
            state.update(native=str(native), native_hash=digest(fixed), native_root=str(fixed))
        # Repair creates a new audit, so attach ancillary checks afterwards.
        report["requirements"] = audit_requirements(native, profile)
        from .fonts import check_fonts
        report["fonts"] = check_fonts(profile) if source.suffix.lower() == ".docx" else {"status": "NOT_APPLICABLE", "reason": "TeX fonts are checked by the isolated compiler log and page review"}
        if native.suffix.lower() == ".docx":
            from .fields import _toc_fields, refresh_fields
            from .word import _package, _xml
            if _toc_fields(_xml(_package(native)["word/document.xml"])):
                if "field-refresh.json" not in state["artifacts"]:
                    _record(state, "REPAIR", {"operation": "refresh_toc_cache", "limit": 3})
                    refreshed_path = directory / "fields-refreshed.docx"
                    sidecar = refreshed_path.with_suffix(".docx.fields.json")
                    if refreshed_path.exists() and sidecar.exists():
                        refreshed = read_json(sidecar)
                        if refreshed.get("output_sha256") != digest(refreshed_path) or refreshed.get("source_sha256") != digest(native):
                            raise ValueError("Interrupted field refresh output failed identity checks")
                    else:
                        refreshed = refresh_fields(native, refreshed_path)
                    if refreshed["status"] == "PASS":
                        native = refreshed_path
                        state.update(native=str(native), native_hash=digest(native), native_root=str(native))
                    _artifact(state, "field-refresh.json", refreshed)
                else:
                    refreshed = read_json(directory / "field-refresh.json")
                report["field_refresh"] = refreshed
                refreshed_audit = audit(source, native, profile)
                report["content"], report["style"] = refreshed_audit["content"], refreshed_audit["style"]
        _record(state, "RENDER")
        if "render.json" in state["artifacts"]:
            rendered = read_json(directory / "render.json")
            validate_rendered_artifacts(rendered)
        else:
            attempt = state.get("render_attempt", 0) + 1
            if attempt > 3:
                raise ValueError("Render recovery limit reached; inspect retained renderer diagnostics")
            render_path = directory / ("render" if attempt == 1 else f"render-attempt-{attempt}")
            state["render_attempt"] = attempt
            write_json(state["state_path"], state)
            rendered = render(native, render_path, profile)
            paths = [rendered["pdf"]] if rendered.get("pdf") else []
            paths.extend(page["png"] for page in rendered.get("visual", {}).get("pages", []))
            rendered["artifact_hashes"] = {str(path): digest(path) for path in paths}
            _artifact(state, "render.json", rendered)
        _record(state, "VISUAL_AUDIT")
        report["render"] = rendered
        if native.suffix.lower() == ".docx" and rendered.get("pdf"):
            from .fonts import audit_rendered_fonts
            report["rendered_fonts"] = audit_rendered_fonts(native, rendered["pdf"], profile)
        report["visual"] = rendered.get("visual", {"status": "UNVERIFIED", "reason": rendered.get("reason")})
        _record(state, "FINAL_GATE")
        final_gate(report)
        report["completeness"] = {"status": "UNKNOWN" if read_json(directory / "missing.json")["issues"] else "PASS",
                                   "report": str(directory / "missing.json"),
                                   "scope": "Genre-dependent findings are advisory in format_only mode"}
        _artifact(state, "audit.json", report)
        result = {"status": report["status"], "output": str(native), "report": str(directory / "audit.json"),
                  "missing": str(directory / "missing.json"), "state": state["state_path"],
                  "unresolved": report["unresolved"]}
        state["finished"], state["result"] = True, result
        _record(state, "DELIVER", result)
        return result
    except Exception as exc:
        state["error"] = {"type": type(exc).__name__, "message": str(exc)}
        write_json(state["state_path"], state)
        raise
