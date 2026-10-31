"""Official-document runs with real rendering and explicit visual acceptance."""
from __future__ import annotations

from pathlib import Path
import re

from .io import digest, read_json, write_json


def _status(value):
    return value.get("status", "UNVERIFIED") if isinstance(value, dict) else value


def _overall(checks):
    values = [_status(value) for value in checks]
    if "FAIL" in values:
        return "FAIL"
    return "PASS" if values and all(value in {"PASS", "NOT_APPLICABLE"} for value in values) else "UNVERIFIED"


def _page_geometry(rendered, plan=None):
    """Physical PDF checks only; image review remains a separate gate."""
    pages = rendered.get("visual", {}).get("pages", [])
    checks = []
    page_rule = (plan or {}).get("profile", {}).get("page", {})
    expected_width, expected_height = page_rule.get("width_mm", 210), page_rule.get("height_mm", 297)
    for page in pages:
        width = page["width_pt"] * 25.4 / 72
        height = page["height_pt"] * 25.4 / 72
        checks.append({"page": page["page"], "name": "paper_size", "width_mm": width,
                       "height_mm": height, "expected_mm": [expected_width, expected_height],
                       "status": "PASS" if abs(width - expected_width) < 1 and abs(height - expected_height) < 1 else "FAIL"})
    if rendered.get("visual", {}).get("geometry") == "FAIL":
        checks.append({"name": "page_overflow", "status": "FAIL"})
    if plan and plan.get("request", {}).get("scope") == "full" and rendered.get("pdf"):
        checks.extend(_line_geometry(rendered["pdf"], page_rule))
    return {"status": _overall(checks), "checks": checks,
            "scope": "PDF page dimensions, text bounds and full-layout rule geometry; typography and overlaps require page review"}


def _line_geometry(pdf, page_rule):
    import ctypes
    import pypdfium2 as pdfium
    from pypdfium2 import raw

    scale = 25.4 / 72
    left = page_rule.get("margin_left_mm", 28)
    width = page_rule.get("width_mm", 210) - left - page_rule.get("margin_right_mm", 26)
    bottom = page_rule.get("margin_bottom_mm", 35)
    lines = []
    with pdfium.PdfDocument(pdf) as document:
        for index in {0, len(document) - 1}:
            page = document[index]
            for obj in page.get_objects():
                if obj.type != raw.FPDF_PAGEOBJ_PATH:
                    continue
                x0, y0, x1, y1 = obj.get_bounds()
                if x1 - x0 < 100 or y1 - y0 > 4:
                    continue
                rgba = [ctypes.c_uint() for _ in range(4)]
                raw.FPDFPageObj_GetFillColor(obj.raw, *[ctypes.byref(c) for c in rgba])
                color = [c.value for c in rgba[:3]]
                lines.append({"page": index + 1, "left_mm": x0 * scale, "width_mm": (x1 - x0) * scale,
                              "bottom_mm": (y0 + y1) / 2 * scale, "color": color})
            page.close()
        red = [line for line in lines if line["page"] == 1 and line["color"][0] > 180 and max(line["color"][1:]) < 80]
        black = [line for line in lines if line["page"] == len(document) and max(line["color"]) < 80]
    checks = []
    for name, candidates in (("header_rule_width", red), ("imprint_bottom_rule", black)):
        selected = min(candidates, key=lambda line: abs(line["bottom_mm"] - bottom)) if candidates else None
        passed = selected is not None and abs(selected["left_mm"] - left) < 1 and abs(selected["width_mm"] - width) < 1
        if name == "imprint_bottom_rule":
            passed = passed and abs(selected["bottom_mm"] - bottom) < 1
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "observed": selected,
                       "expected": {"left_mm": left, "width_mm": width, "bottom_mm": bottom if name == "imprint_bottom_rule" else None}})
    return checks


def _layout_checks(plan, layout):
    """Verify source role positions against Word's actual pagination."""
    if layout.get("status") not in {"PASS", "FAIL"}:
        return layout
    from .official import inspect_official

    blocks = inspect_official(plan["source"], plan["request"])["blocks"]
    paragraphs = layout.get("paragraphs", [])
    checks = []
    matched = []
    cursor = 0
    for block in blocks:
        role = plan["roles"].get(block["id"], block["role"])
        text = block["text"].strip()
        found = next((i for i in range(cursor, len(paragraphs)) if paragraphs[i]["text"].strip() == text), None) if text else None
        if found is not None:
            matched.append((role, paragraphs[found]))
            cursor = found + 1
        elif text:
            matched.append((role, None))
    first_body = next((p for role, p in matched if role == "body"), None)
    checks.append({"name": "body_on_first_page", "status": "PASS" if first_body and first_body["page"] == 1 else "FAIL",
                   "page": first_body["page"] if first_body else None})
    for index, (role, paragraph) in enumerate(matched):
        if role != "attachment_label":
            continue
        previous = matched[index - 1][1] if index else None
        following = matched[index + 1] if index + 1 < len(matched) else None
        passed = paragraph is not None and previous is not None and paragraph["page"] > previous["page"]
        passed = passed and following is not None and following[0] == "attachment_title" and following[1] is not None and following[1]["page"] == paragraph["page"]
        checks.append({"name": "attachment_new_page", "label": paragraph["text"] if paragraph else None, "page": paragraph["page"] if paragraph else None,
                       "status": "PASS" if passed else "FAIL"})
    return {**layout, "official_checks": checks, "status": _overall([layout, *checks])}


def _output_roles(plan, native):
    """Keep the approved official roles when querying rendered source glyphs."""
    from .word import _package, _xml, NS

    root = _xml(_package(native)["word/document.xml"])
    result = {}
    source_index = 0
    for index, paragraph in enumerate(root.findall(".//w:body//w:p", NS)):
        marks = paragraph.xpath(".//w:bookmarkStart/@w:name", namespaces=NS)
        generated = next((re.fullmatch(r"_MWOFF_(.+)_\d+", name) for name in marks if re.fullmatch(r"_MWOFF_(.+)_\d+", name)), None)
        if generated:
            result[f"p{index}"] = generated.group(1)
        else:
            result[f"p{index}"] = plan["roles"].get(f"p{source_index}", "unknown")
            source_index += 1
    return result


def run_official(source, output, request=None, roles=None, renderer="auto"):
    from .official import plan_official, apply_official, audit_official, finalize_layout
    from .render import render
    from .fonts import check_fonts

    source, directory = Path(source).resolve(), Path(output).resolve()
    if directory.exists():
        raise FileExistsError("Official run directory must be new")
    if directory == source or source in directory.parents:
        raise ValueError("Run output must be outside the source")
    plan = plan_official(source, request, roles)
    directory.mkdir(parents=True)
    write_json(directory / "plan.json", plan)
    if plan.get("status") != "PASS":
        result = {"status": "NEEDS_INPUT", "plan": str(directory / "plan.json"),
                  "issues": plan.get("issues", []), "output": None}
        write_json(directory / "report.json", result)
        return result
    native = directory / "editable.docx"
    applied = apply_official(plan, native)
    layout = _layout_checks(plan, finalize_layout(native))
    write_json(directory / "apply.json", applied)
    write_json(directory / "layout.json", layout)
    report = audit_official(source, native, plan.get("request", request), plan.get("roles", roles))
    profile = plan.get("profile") or applied.get("profile")
    if profile is None:
        from .official_models import OfficialRequest
        config = OfficialRequest.model_validate(plan.get("request", request) or {})
        profile = {"rules": {key: {"east_asia_font": font} for key, font in config.fonts.model_dump().items()}}
    report["fonts"] = check_fonts(profile)
    report["target"] = {"standard": "GB/T 9704-2012", "scope": plan["request"].get("scope", "body"),
                        "mode": plan["request"].get("mode", "standard"),
                        "font_overrides": profile.get("font_overrides", {}),
                        "template_differences": plan.get("template", {}).get("differences", []),
                        "status_scope": "Checks apply to the selected requirements, including the recorded overrides"}
    # Generic paper heuristics identify recipients and numbered body paragraphs
    # differently. Font evidence must use the approved official role mapping.
    rendered = render(native, directory / "render", None, renderer)
    if rendered.get("status") == "PASS" and rendered.get("pdf"):
        from .fonts import audit_rendered_fonts
        rendered["fonts"] = audit_rendered_fonts(native, rendered["pdf"], profile, _output_roles(plan, native))
    report["render"] = {key: value for key, value in rendered.items() if key != "visual"}
    report["geometry"] = _page_geometry(rendered, plan)
    report["layout"] = layout
    report["visual"] = {"status": "UNVERIFIED", "reason": "Review every rendered page and submit official accept"}
    if "fonts" in rendered:
        report["rendered_fonts"] = rendered["fonts"]
    checks = [report.get(key, "UNVERIFIED") for key in ("content", "style", "structure", "fonts", "visual", "geometry")]
    checks.extend([rendered, layout])
    if "rendered_fonts" in report:
        checks.append(report["rendered_fonts"])
    report["status"] = _overall(checks)
    write_json(directory / "render.json", rendered)
    write_json(directory / "audit.json", report)
    result = {"status": report["status"], "output": str(native), "pdf": rendered.get("pdf"),
              "report": str(directory / "audit.json"), "layout": layout,
              "font_overrides": report["target"]["font_overrides"],
              "template_difference_count": len(report["target"]["template_differences"]),
              "issues": plan.get("issues", []), "visual": report["visual"]}
    write_json(directory / "report.json", result)
    state = {"source": str(source), "source_hash": digest(source), "native": str(native),
             "native_hash": digest(native), "artifacts": {name: digest(directory / name) for name in
                ("plan.json", "apply.json", "layout.json", "render.json", "audit.json", "report.json")}}
    if rendered.get("pdf"):
        state["pdf_hash"] = digest(rendered["pdf"])
    write_json(directory / "state.json", state)
    return result


def accept_official(directory, review):
    from .review import VisualReview

    directory = Path(directory).resolve()
    state = read_json(directory / "state.json")
    if digest(state["source"]) != state["source_hash"] or digest(state["native"]) != state["native_hash"]:
        raise ValueError("Source or official output changed after rendering")
    for name, expected in state["artifacts"].items():
        if digest(directory / name) != expected:
            raise ValueError(f"Official run artifact changed: {name}")
    rendered = read_json(directory / "render.json")
    if rendered.get("status") != "PASS" or not rendered.get("pdf"):
        raise ValueError("A successful real render is required")
    if digest(rendered["pdf"]) != state.get("pdf_hash"):
        raise ValueError("Rendered PDF changed")
    verified = VisualReview.model_validate(review)
    if verified.source_sha256 != state["native_hash"]:
        raise ValueError("Review source hash does not match the official output")
    pages = rendered.get("visual", {}).get("pages", [])
    expected = {page["page"]: page for page in pages}
    if len(verified.pages) != len(pages) or {page.page for page in verified.pages} != set(expected):
        raise ValueError("Review must cover every rendered page exactly once")
    values = []
    for page in verified.pages:
        saved = expected[page.page]
        if page.sha256 != saved["sha256"] or digest(saved["png"]) != page.sha256:
            raise ValueError("Review image hash mismatch")
        values.extend(page.checks.model_dump().values())
    report = read_json(directory / "audit.json")
    report["visual"] = {"status": _overall(values), "review": verified.model_dump(mode="json")}
    checks = [report.get(key, "UNVERIFIED") for key in
              ("content", "style", "structure", "fonts", "visual", "geometry", "render", "layout")]
    if "rendered_fonts" in report:
        checks.append(report["rendered_fonts"])
    report["status"] = _overall(checks)
    result = read_json(directory / "report.json")
    result.update(status=report["status"], visual=report["visual"])
    write_json(directory / "visual-review.json", verified.model_dump(mode="json"))
    write_json(directory / "audit.json", report)
    write_json(directory / "report.json", result)
    for name in ("audit.json", "report.json", "visual-review.json"):
        state["artifacts"][name] = digest(directory / name)
    write_json(directory / "state.json", state)
    return result
