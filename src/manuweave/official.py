"""Native, content-preserving GB/T 9704 document formatting.

Semantic choices are explicit in the plan. Geometry and visual acceptance remain
separate from XML formatting checks. No arbitrary code or remote service is used.
"""
from __future__ import annotations

import copy
import math
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

from lxml import etree as ET

from .io import digest
from .official_models import OfficialPlan, OfficialRequest
from .word import NS, W, _Styles, _canonical, _child, _ensure, _package, _set_format, _set_page_properties, _xml

REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
R = "{" + NS["r"] + "}"
PITCH = 225 / 25.4 * 72 / 22
PAGE = {"width_mm": 210, "height_mm": 297, "margin_top_mm": 37, "margin_bottom_mm": 35,
        "margin_left_mm": 28, "margin_right_mm": 26, "columns": 1,
        "grid_type": "linesAndChars", "grid_line_pitch_pt": PITCH, "footer_distance_mm": 23}
SOURCE = "https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=F3CC9BEF482524C895FDA7A08BB4A70E"
_DATE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")
_DATE_CANDIDATE = re.compile(r"^[0-9〇○零一二三四五六七八九十]{4}年[0-9〇○零一二三四五六七八九十]{1,3}月[0-9〇○零一二三四五六七八九十]{1,3}日$")
_DOCNO = re.compile(r"[^\s]+〔[0-9]{4}〕[1-9][0-9]*号")
_DOCNO_CANDIDATE = re.compile(r"^[\u3400-\u9fffA-Za-z][\u3400-\u9fffA-Za-z0-9·-]{0,39}[〔\[［【（(]\s*[0-9〇○零一二三四五六七八九十]{2,4}\s*[〕\]］】）)]\s*(?:第\s*)?[0-9]+号$")
_MANAGED = "_MWOFF_"


def _character_grid(parts, page):
    width = page["width_mm"] - page["margin_left_mm"] - page["margin_right_mm"]
    # Every managed body paragraph explicitly sets its paragraph-mark font to
    # 16pt. Word uses that base for its active character grid, including sources
    # whose docDefaults remain 11pt. This is verified with rendered 28-char rows.
    default_size = 16
    return str(round((width / 25.4 * 72 / 28 - default_size) * 4096))


def _request(request=None):
    return OfficialRequest.model_validate(request or {}).model_dump(mode="json")


def _issue(code, message, block_ids=None):
    return {"id": code, "category": "needs_user", "detail": message, "block_ids": block_ids or []}


def _text(p):
    return "".join(p.xpath(".//w:t/text()", namespaces=NS))


def _managed(node):
    return bool(node.xpath(".//w:bookmarkStart[starts-with(@w:name, '_MWOFF_')]", namespaces=NS))


def _guess(paragraphs, request):
    metadata = request["metadata"]
    roles = {}
    body = next(iter(paragraphs), None)
    parent = body.getparent() if body is not None else None
    awaiting_attachment_title = False
    title_found = False
    for index, p in enumerate(paragraphs):
        text = _text(p).strip()
        role = "body"
        if not text:
            role = "image" if p.findall(".//w:drawing", NS) or p.findall(".//w:pict", NS) else "blank"
        elif any(a.tag == W + "tc" for a in p.iterancestors()):
            role = "table_body"
        elif p.getparent() is not parent:
            role = "unknown"
        elif re.match(r"^抄送[：:]", text):
            role = "copy_to"
        elif re.search(r"\d{4}年\d{1,2}月\d{1,2}日印发$", text):
            role = "print_line"
        elif _DATE.fullmatch(text) or _DATE_CANDIDATE.fullmatch(text):
            role = "date"
        elif re.match(r"^附件\s*[：:]", text):
            role = "attachment_note"
        elif re.match(r"^\d+[.．、]\s*", text) and next((roles[f"p{i}"] for i in range(index - 1, -1, -1) if roles[f"p{i}"] != "blank"), None) == "attachment_note":
            role = "attachment_note"
        elif re.fullmatch(r"附件\s*\d*", text):
            role = "attachment_label"
            awaiting_attachment_title = True
        elif awaiting_attachment_title:
            role = "attachment_title"
            awaiting_attachment_title = False
        elif re.match(r"^签发人[：:]", text):
            role = "signatory"
        elif _DOCNO.fullmatch(text) or _DOCNO_CANDIDATE.fullmatch(text):
            role = "document_number"
        elif not title_found and (text.endswith("文件") or text == metadata.get("issuing_authority")):
            role = "issuing_authority"
        elif re.match(r"^[一二三四五六七八九十百]+[、．]", text):
            role = "heading1"
        elif re.match(r"^[（(][一二三四五六七八九十百]+[）)]", text):
            role = "heading2"
        elif re.match(r"^\d+[.．、]", text):
            role = "heading3"
        elif re.match(r"^[（(]\d+[）)]", text):
            role = "heading4"
        elif not title_found:
            role = "title"
            title_found = True
        elif text.endswith(("：", ":")) and not any(r == "recipient" for r in roles.values()):
            # A recipient is expected immediately after the title, not in later prose.
            previous = next((roles[f"p{i}"] for i in range(index - 1, -1, -1) if roles[f"p{i}"] != "blank"), None)
            role = "recipient" if previous == "title" else "body"
        elif text.startswith("（") and text.endswith("）") and "date" in roles.values():
            role = "note"
        roles[f"p{index}"] = role
    # The paragraph immediately before a date is an issuing signature only when
    # it is a short unstructured line. The resulting inference is exposed.
    for index, p in enumerate(paragraphs):
        if roles[f"p{index}"] != "date":
            continue
        previous = next((i for i in range(index - 1, -1, -1) if roles[f"p{i}"] != "blank"), None)
        if previous is not None and roles[f"p{previous}"] == "body":
            value = _text(paragraphs[previous]).strip()
            if len(value) <= 60 and not re.search(r"[。；：！？]", value):
                roles[f"p{previous}"] = "signature"
    return roles


def _inspect(source, request, roles=None):
    source = Path(source).resolve()
    if source.suffix.lower() != ".docx":
        raise ValueError("Official formatting requires a native DOCX source")
    parts = _package(source)
    root = _xml(parts["word/document.xml"])
    paragraphs = root.findall(".//w:body//w:p", NS)
    mapped = _guess(paragraphs, request)
    if set(roles or {}) - set(mapped):
        raise ValueError("Official role map contains unknown paragraph IDs")
    mapped.update(roles or {})
    # Validate role names through the public contract, including an empty document.
    OfficialPlan(source=str(source), source_hash=digest(source), request=request, roles=mapped, status="PASS")
    styles = _Styles(parts)
    blocks = [{"id": f"p{i}", "role": mapped[f"p{i}"], "text": _text(p),
               "source": {"part": "word/document.xml", "xpath": root.getroottree().getpath(p)},
               "format": styles.effective(p)} for i, p in enumerate(paragraphs)]
    issues = []
    if any(re.fullmatch(r"word/mwOfficialFooter\d+\.xml", name) for name in parts):
        issues.append(_issue("already_formatted", "Use the original source for a fresh official formatting plan."))
    if len(root.findall(".//w:sectPr", NS)) != 1:
        issues.append(_issue("complex_sections", "Existing multiple sections require a dedicated layout; no changes will be applied."))
    if any(_managed(p) for p in paragraphs):
        issues.append(_issue("already_formatted", "This document contains a managed official layout; use its original source for a new plan."))
    for name, data in parts.items():
        if re.fullmatch(r"word/header\d*\.xml", name):
            header = _xml(data)
            if header.xpath(".//w:t[string-length(normalize-space(.)) > 0] | .//w:fldSimple | .//w:instrText | .//w:drawing | .//w:pict | .//m:oMath | .//w:object", namespaces=NS):
                issues.append(_issue("existing_header", "Existing header content requires a dedicated official layout integration."))
                break
        if re.fullmatch(r"word/footer\d*\.xml", name):
            footer = _xml(data)
            if footer.xpath(".//w:t[string-length(normalize-space(.)) > 0] | .//w:fldSimple | .//w:instrText | .//w:drawing | .//w:pict | .//m:oMath | .//w:object", namespaces=NS):
                issues.append(_issue("existing_footer", "Existing footer content requires explicit integration before official page numbers can be installed."))
                break
    if any(b["role"] == "unknown" for b in blocks):
        issues.append(_issue("nested_content", "Paragraphs in content controls or nested structures require explicit role mapping.", [b["id"] for b in blocks if b["role"] == "unknown"]))
    if root.xpath(".//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo", namespaces=NS):
        issues.append(_issue("tracked_changes", "Resolve tracked changes in a separate source copy before official formatting."))
    if not any(b["role"] == "title" for b in blocks):
        issues.append(_issue("missing_title", "No title was identified; supply an explicit role map."))
    if not any(b["role"] in {"body", "heading1", "heading2", "heading3", "heading4"} and b["text"].strip() for b in blocks):
        issues.append(_issue("missing_body", "No body text was identified."))
    notes = [b for b in blocks if b["role"] == "attachment_note"]
    labels = [b for b in blocks if b["role"] == "attachment_label"]
    if notes and not labels:
        issues.append(_issue("missing_attachment", "Attachment descriptions exist but no attachment body was identified.", [b["id"] for b in notes]))
    if len([b for b in blocks if b["role"] == "attachment_title"]) < len(labels):
        issues.append(_issue("missing_attachment_title", "An attachment label has no following attachment title."))
    if notes and labels:
        expected_attachments = []
        for note in notes:
            value = re.sub(r"^附件\s*[：:]\s*", "", note["text"].strip())
            match = re.match(r"^(\d+)[.．、]\s*(.+)$", value)
            expected_attachments.append((int(match.group(1)), match.group(2).strip()) if match else (1, value.strip()))
        actual_attachments = []
        for label in labels:
            pos = blocks.index(label)
            title = next((b for b in blocks[pos + 1:] if b["role"] != "blank"), None)
            match = re.fullmatch(r"附件\s*(\d*)", label["text"].strip())
            if title and title["role"] == "attachment_title" and match:
                actual_attachments.append((int(match.group(1) or 1), title["text"].strip()))
        if expected_attachments != actual_attachments:
            issues.append(_issue("attachment_mismatch", "Attachment description numbers and titles must match the attached bodies.", [b["id"] for b in notes + labels]))
    dates = [b for b in blocks if b["role"] == "date"]
    print_dates = [re.search(r"([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)印发$", b["text"].strip()) for b in blocks if b["role"] == "print_line"]
    for value in [request["metadata"].get("date"), request["metadata"].get("print_date")] + [b["text"].strip() for b in dates] + [match.group(1) for match in print_dates if match]:
        if value:
            match = _DATE.fullmatch(value)
            try:
                if match is None:
                    raise ValueError
                date(*map(int, match.groups()))
                if any(len(part) > 1 and part.startswith("0") for part in match.groups()[1:]):
                    raise ValueError
            except ValueError:
                issues.append(_issue("invalid_date", "Dates require a real calendar date in YYYY年M月D日 form with Arabic digits and no zero-padded month or day; confirm normalization explicitly."))
    number_values = [(request["metadata"].get("document_number"), [])]
    number_values += [(b["text"].strip(), [b["id"]]) for b in blocks if b["role"] == "document_number"]
    for value, block_ids in number_values:
        if value and not _DOCNO.fullmatch(value):
            issues.append(_issue("invalid_document_number", "A document number requires a full year in 〔〕 and a non-padded sequence ending in 号; confirm normalization explicitly.", block_ids))
    if request["scope"] == "full":
        if request["direction"] == "up" and any(b["role"] == "signatory" for b in blocks):
            issues.append(_issue("separate_signatory", "A standalone signatory row needs explicit same-line integration with the document number before full upward formatting."))
        field_roles = {"issuing_authority": {"issuing_authority", "signature"}, "document_number": {"document_number"}, "date": {"date"}, "signatory": {"signatory"}}
        for field, candidates in field_roles.items():
            supplied = request["metadata"].get(field)
            if not supplied:
                continue
            for b in blocks:
                if b["role"] not in candidates:
                    continue
                existing = b["text"].strip()
                if field == "issuing_authority":
                    existing = existing.removesuffix("文件")
                    supplied = supplied.removesuffix("文件")
                if field == "signatory":
                    existing = re.sub(r"^签发人[：:]\s*", "", existing)
                if existing != supplied:
                    issues.append(_issue("conflicting_" + field, "Source and supplied " + field + " differ; confirm the source or metadata before formatting.", [b["id"]]))
        requirements = [("issuing_authority", {"issuing_authority", "signature"}), ("document_number", {"document_number"}),
                        ("date", {"date"}), ("print_authority", {"print_line"}), ("print_date", {"print_line"})]
        if request["direction"] == "up":
            requirements.append(("signatory", {"signatory"}))
        for field, candidates in requirements:
            if not request["metadata"].get(field) and not any(b["role"] in candidates for b in blocks):
                issues.append(_issue("missing_" + field, "Full layout requires confirmed " + field + " from source text or metadata."))
        for role in ("issuing_authority", "document_number", "signature", "date", "print_line"):
            matches = [b for b in blocks if b["role"] == role]
            if len(matches) > 1:
                issues.append(_issue("ambiguous_" + role, "Multiple " + role + " paragraphs require a role map.", [b["id"] for b in matches]))
    return {"kind": "docx", "document_type": "official", "source": str(source), "sha256": digest(source),
            "blocks": blocks, "roles": mapped, "issues": issues, "status": "NEEDS_INPUT" if issues else "PASS",
            "standard": "GB/T 9704-2012", "standard_source": SOURCE}


def inspect_official(source, request=None):
    """Inspect public official roles and conditional missing information."""
    return _inspect(source, _request(request))


def _rules(request):
    fonts = request["fonts"]
    body = {"font": fonts["body"], "east_asia_font": fonts["body"], "size_pt": 16,
            "alignment": "justify", "line_spacing_rule": "exact", "line_spacing_pt": PITCH,
            "space_before_pt": 0, "space_after_pt": 0, "first_line_pt": 32,
            "left_indent_pt": 0, "right_indent_pt": 0, "font_color": "000000", "bold": False}
    rules = {role: dict(body) for role in ("body", "heading1", "heading2", "heading3", "heading4", "recipient", "signature", "date", "note", "attachment_note", "attachment_label", "attachment_title", "document_number", "signatory", "copy_to", "print_line", "issuing_authority", "title")}
    for role in ("heading1", "heading2"):
        rules[role].update(font=fonts[role], east_asia_font=fonts[role])
    rules["title"].update(font=fonts["title"], east_asia_font=fonts["title"], size_pt=22, alignment="center", first_line_pt=0, line_spacing_pt=32, space_after_pt=PITCH)
    rules["attachment_title"].update(rules["title"], space_before_pt=PITCH, space_after_pt=PITCH)
    rules["recipient"].update(alignment="left", first_line_pt=0, space_after_pt=0)
    rules["attachment_note"].update(space_before_pt=PITCH)
    rules["attachment_label"].update(font=fonts["heading1"], east_asia_font=fonts["heading1"], first_line_pt=0, alignment="left")
    rules["issuing_authority"].update(font=fonts["title"], east_asia_font=fonts["title"], font_color="FF0000", size_pt=32, alignment="center", first_line_pt=0, line_spacing_pt=40, space_before_pt=35 / 25.4 * 72, space_after_pt=PITCH * 2)
    rules["document_number"].update(alignment="left" if request["direction"] == "up" else "center", first_line_pt=16 if request["direction"] == "up" else 0, left_indent_pt=1.5, right_indent_pt=1.5, space_after_pt=PITCH * 2)
    rules["signatory"].update(alignment="right", first_line_pt=0)
    for role in ("signature", "date"):
        rules[role].update(alignment="right", first_line_pt=0, right_indent_pt=32)
    rules["signature"].update(space_before_pt=PITCH)
    if request["seal_mode"] == "reserved":
        rules["date"].update(right_indent_pt=64)
        rules["signature"].update(space_before_pt=PITCH * 2, right_indent_pt=64)
    rules["copy_to"].update(size_pt=14, first_line_pt=0, left_indent_pt=14, right_indent_pt=14, line_spacing_pt=20)
    rules["print_line"].update(rules["copy_to"])
    return rules


def _learn_template(request):
    reference = request["reference"]
    inspected = _inspect(reference, {**request, "scope": "body", "mode": "standard", "reference": None, "reference_roles": {}, "metadata": {}}, request["reference_roles"])
    rules = _rules(request)
    learned = {}
    differences = []
    for role in rules:
        values = [b["format"] for b in inspected["blocks"] if b["role"] == role and b["text"].strip()]
        if not values:
            continue
        learned[role] = {}
        for key in set(rules[role]) | {"line_spacing"}:
            available = [value[key] for value in values if key in value]
            if not available:
                continue
            selected = Counter(available).most_common(1)[0][0]
            learned[role][key] = selected
            if selected != rules[role].get(key):
                differences.append({"role": role, "property": key, "standard": rules[role].get(key), "template": selected})
    parts = _package(reference)
    from .word import _page
    sections = _xml(parts["word/document.xml"]).findall(".//w:sectPr", NS)
    page = _page(sections[0]) if len(sections) == 1 else {}
    for key in PAGE:
        if key in page and page[key] != PAGE[key]:
            differences.append({"role": "page", "property": key, "standard": PAGE[key], "template": page[key]})
    return {"source": str(Path(reference).resolve()), "sha256": digest(reference), "rules": learned,
            "page": {key: page[key] for key in PAGE if key in page}, "differences": differences,
            "scope": "Extracted official-role font and paragraph values plus page geometry; template text and objects are not copied."}


def plan_official(source, request=None, roles=None):
    request = _request(request)
    inspected = _inspect(source, request, roles)
    template = _learn_template(request) if request["mode"] == "template" else {}
    return OfficialPlan(source=inspected["source"], source_hash=inspected["sha256"], request=request,
                        roles=inspected["roles"], issues=inspected["issues"], status=inspected["status"],
                        reference_hash=template.get("sha256"), template=template,
                        profile=official_profile(request, template)).model_dump(mode="json")


def official_profile(request=None, template=None):
    request = _request(request)
    rules = _rules(request)
    for role, properties in (template or {}).get("rules", {}).items():
        _merge_rule(rules[role], properties)
    rules["page_number"] = {"font": request["fonts"]["page_number"], "east_asia_font": request["fonts"]["page_number"], "size_pt": 14}
    overrides = {name: {"default": value, "selected": request["fonts"][name]}
                 for name, value in OfficialRequest().fonts.model_dump().items() if request["fonts"][name] != value}
    return {"id": "cn-official-gbt9704-2012", "name": "党政机关公文格式", "version": "1.0.0",
            "document_type": "official", "rules": rules, "page": {**PAGE, **(template or {}).get("page", {})},
            "sources": [{"url": SOURCE, "standard": "GB/T 9704-2012"}], "font_overrides": overrides}


def _merge_rule(rule, properties):
    if properties.get("line_spacing_rule") == "auto" or "line_spacing" in properties:
        rule.pop("line_spacing_pt", None)
    elif "line_spacing_pt" in properties:
        rule.pop("line_spacing", None)
    rule.update(properties)


def _mark(node, label, ident):
    p = node if node.tag == W + "p" else node.find(".//w:p", NS)
    start = ET.Element(W + "bookmarkStart", {W + "id": str(ident), W + "name": _MANAGED + label})
    end = ET.Element(W + "bookmarkEnd", {W + "id": str(ident)})
    p.insert(1 if _child(p, "pPr") is not None else 0, start)
    p.append(end)


def _paragraph(text):
    p = ET.Element(W + "p")
    run = ET.SubElement(p, W + "r")
    ET.SubElement(run, W + "t").text = text
    return p


def _set_role(p, role, rules, width_pt=156 / 25.4 * 72):
    if role not in rules:
        return
    properties = _block_rule(role, _text(p), rules, width_pt)
    _set_format(p, properties)
    prop = _ensure(p, "pPr")
    _ensure(prop, "adjustRightInd").set(W + "val", "0")
    # A source Title style can carry a blue horizontal rule. Explicit nil edges
    # suppress inherited decoration before official red/imprint rules are added.
    borders = _ensure(prop, "pBdr")
    for edge in ("top", "left", "bottom", "right", "between", "bar"):
        _ensure(borders, edge).set(W + "val", "nil")
    # Explicitly override inherited outline, auto-spacing and numeric indentation.
    grid_role = role in {"body", "heading1", "heading2", "heading3", "heading4"} and abs(properties.get("line_spacing_pt", 0) - PITCH) < 0.02
    _ensure(prop, "snapToGrid").set(W + "val", "1" if grid_role else "0")
    for attr in ("beforeAutospacing", "afterAutospacing", "beforeLines", "afterLines"):
        _ensure(prop, "spacing").attrib.pop(W + attr, None)
    if role.startswith("heading") or role in {"title", "attachment_label", "attachment_title", "signature"}:
        _ensure(prop, "keepNext").set(W + "val", "1")
        _ensure(prop, "keepLines").set(W + "val", "1")
    if role == "attachment_label":
        _ensure(prop, "pageBreakBefore").set(W + "val", "1")
    if role in {"body", "heading1", "heading2", "heading3", "heading4"}:
        if properties.get("first_line_pt") == 32 and properties.get("size_pt") == 16:
            _ensure(prop, "ind").set(W + "firstLineChars", "200")
        if grid_role and properties.get("size_pt") == 16:
            for run in p.findall(".//w:r", NS):
                _ensure(_ensure(run, "rPr"), "spacing").set(W + "val", "-4")


def _block_rule(role, text, rules, width_pt=156 / 25.4 * 72):
    properties = dict(rules.get(role, {}))
    if role in {"title", "attachment_title"}:
        # Balance long titles by controlling the line box, without inserting or
        # deleting a character. Keep common two-character document terms intact.
        size = properties.get("size_pt", 22)
        units = sum(1 if ord(c) > 127 else 0.5 for c in text.strip())
        capacity = max(4, math.floor(width_pt / size) - 1)
        if units > capacity:
            lines = math.ceil(units / capacity)
            target = math.ceil(units / lines)
            protected = {"通知", "报告", "请示", "批复", "意见", "决定", "通报", "公告", "通告", "纪要", "公报", "决议", "议案", "关于", "开展", "工作", "情况", "进展", "安排", "有关", "实施", "管理", "办法", "规定", "方案"}
            if len(text) > target and text[target - 1:target + 1] in protected:
                target += 1
            indent = max(0, (width_pt - target * size - 2) / 2)
            properties.update(left_indent_pt=indent, right_indent_pt=indent)
    elif role == "attachment_note":
        match = re.match(r"^(附件\s*[：:]\s*(?:\d+[.．、]\s*)?|\d+[.．、]\s*)", text.strip())
        if match:
            prefix = sum(1 if ord(c) > 127 else 0.5 for c in match.group(1)) * properties.get("size_pt", 16)
            # Continued names align with the first name, not with 附件 or its number.
            extra = 0 if text.strip().startswith("附件") else 3 * properties.get("size_pt", 16)
            properties.update(left_indent_pt=32 + prefix + extra, first_line_pt=-prefix)
    elif role == "copy_to":
        match = re.match(r"^抄送[：:]\s*", text.strip())
        if match:
            prefix = 3 * properties.get("size_pt", 14)
            properties.update(left_indent_pt=properties.get("left_indent_pt", 14) + prefix, first_line_pt=-prefix)
    return properties


def _border(p, edge, color="000000", size=8, space=0):
    target = _ensure(_ensure(_ensure(p, "pPr"), "pBdr"), edge)
    for key, value in {"val": "single", "sz": str(size), "color": color, "space": str(space)}.items():
        target.set(W + key, value)


def _footer(parts, section, request):
    settings = _xml(parts["word/settings.xml"]) if "word/settings.xml" in parts else ET.Element(W + "settings", nsmap={"w": NS["w"]})
    _ensure(settings, "evenAndOddHeaders").set(W + "val", "1")
    _ensure(settings, "updateFields").set(W + "val", "true")
    parts["word/settings.xml"] = ET.tostring(settings, xml_declaration=True, encoding="UTF-8", standalone=True)
    relname = "word/_rels/document.xml.rels"
    rels = _xml(parts[relname]) if relname in parts else ET.Element("{" + REL + "}Relationships", nsmap={None: REL})
    content = _xml(parts["[Content_Types].xml"])
    # Existing footers were checked for content. Their package parts remain intact.
    for node in list(section.findall("w:footerReference", NS)):
        section.remove(node)
    title = _child(section, "titlePg")
    if title is not None:
        section.remove(title)
    for kind, align in (("default", "right"), ("even", "left")):
        num = 1
        while f"word/mwOfficialFooter{num}.xml" in parts:
            num += 1
        name = f"mwOfficialFooter{num}.xml"
        rid = "rIdMWOfficial" + str(num)
        ids = {node.get("Id") for node in rels}
        while rid in ids:
            rid += "x"
        footer = ET.Element(W + "ftr", nsmap={"w": NS["w"], "r": NS["r"]})
        p = ET.SubElement(footer, W + "p")
        properties = {"font": request["fonts"]["page_number"], "east_asia_font": request["fonts"]["page_number"],
                      "size_pt": 14, "alignment": align, "first_line_pt": 0,
                      "left_indent_pt": 14 if align == "left" else 0, "right_indent_pt": 14 if align == "right" else 0,
                      "space_before_pt": 0, "space_after_pt": 0, "line_spacing_rule": "exact", "line_spacing_pt": 14}
        p.append(_paragraph("— ")[0])
        field = ET.SubElement(p, W + "fldSimple", {W + "instr": " PAGE ", W + "dirty": "true"})
        field.append(_paragraph("1")[0])
        p.append(_paragraph(" —")[0])
        _set_format(p, properties)
        _mark(p, "page_" + kind, 900000 + num)
        parts["word/" + name] = ET.tostring(footer, xml_declaration=True, encoding="UTF-8", standalone=True)
        ET.SubElement(rels, "{" + REL + "}Relationship", Id=rid, Type=NS["r"] + "/footer", Target=name)
        ET.SubElement(content, "{" + CT + "}Override", PartName="/word/" + name,
                      ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml")
        section.insert(0, ET.Element(W + "footerReference", {W + "type": kind, R + "id": rid}))
    parts[relname] = ET.tostring(rels, xml_declaration=True, encoding="UTF-8", standalone=True)
    parts["[Content_Types].xml"] = ET.tostring(content, xml_declaration=True, encoding="UTF-8", standalone=True)


def _package_write(parts, output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                archive.writestr(name, data)


def _resolved_metadata(inspected, request):
    values = dict(request["metadata"])
    mapping = {"issuing_authority": "signature", "document_number": "document_number", "date": "date", "signatory": "signatory"}
    for field, role in mapping.items():
        if not values.get(field):
            block = next((b for b in inspected["blocks"] if b["role"] == role), None)
            if block:
                values[field] = block["text"].strip()
    if not values.get("issuing_authority"):
        block = next((b for b in inspected["blocks"] if b["role"] == "issuing_authority"), None)
        if block:
            values["issuing_authority"] = block["text"].strip().removesuffix("文件")
    return values


def _signature_rules(rules, metadata, request):
    authority, dated = metadata.get("issuing_authority"), metadata.get("date")
    if not authority or not dated:
        return
    def width(text):
        return sum(1 if ord(c) > 127 else 0.5 for c in text) * 16
    authority_width, date_width = width(authority), width(dated)
    if request["seal_mode"] == "reserved":
        rules["date"]["right_indent_pt"] = 64
        rules["signature"]["right_indent_pt"] = max(0, 64 + (date_width - authority_width) / 2)
    elif date_width > authority_width:
        rules["date"]["right_indent_pt"] = 32
        rules["signature"]["right_indent_pt"] = 32 + date_width - authority_width + 32
    else:
        rules["signature"]["right_indent_pt"] = 32
        rules["date"]["right_indent_pt"] = max(32, 32 + authority_width - date_width - 32)


def apply_official(plan, output):
    """Apply a validated plan to a new package without rebuilding source content."""
    validated = OfficialPlan.model_validate(plan)
    plan = validated.model_dump(mode="json")
    source = Path(plan["source"])
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Official output already exists")
    if source.resolve() == output:
        raise ValueError("Official output must differ from source")
    if digest(source) != plan["source_hash"]:
        raise ValueError("Source changed since official planning")
    request = plan["request"]
    if request["reference"] and digest(request["reference"]) != plan["reference_hash"]:
        raise ValueError("Reference changed since official planning")
    # Recompute missing requirements; editing a plan's status cannot bypass them.
    inspected = _inspect(source, request, plan["roles"])
    if inspected["issues"]:
        raise ValueError("Official layout needs input: " + "; ".join(item["id"] for item in inspected["issues"]))
    if request["mode"] == "template" and _learn_template(request) != plan["template"]:
        raise ValueError("Template requirements differ from the verified reference")
    parts = _package(source)
    root = _xml(parts["word/document.xml"])
    body = root.find("w:body", NS)
    paragraphs = root.findall(".//w:body//w:p", NS)
    rules = _rules(request)
    metadata = _resolved_metadata(inspected, request)
    _signature_rules(rules, metadata, request)
    for role, properties in plan["template"].get("rules", {}).items():
        _merge_rule(rules[role], properties)
    page = {**PAGE, **plan["template"].get("page", {})}
    width_pt = (page["width_mm"] - page["margin_left_mm"] - page["margin_right_mm"]) / 25.4 * 72
    section = root.find(".//w:sectPr", NS)
    _set_page_properties(section, page)
    grid = _ensure(section, "docGrid")
    grid.set(W + "charSpace", _character_grid(parts, page))
    numbering = _child(section, "pgNumType")
    if numbering is not None:
        numbering.attrib.pop(W + "start", None)
    changes = []
    nodes = {}
    for block, p in zip(inspected["blocks"], paragraphs):
        role = block["role"]
        nodes.setdefault(role, []).append(p)
        _set_role(p, role, rules, width_pt)
        changes.append({"id": block["id"], "role": role, "operation": "official_format"})
        if role in {"title", "attachment_title"}:
            title_rule = _block_rule(role, block["text"], rules, width_pt)
            if title_rule.get("left_indent_pt", 0):
                changes.append({"id": block["id"], "operation": "balance_title_line_box",
                                "left_indent_pt": title_rule["left_indent_pt"], "right_indent_pt": title_rule["right_indent_pt"],
                                "text_changed": False})
    _footer(parts, section, request)
    next_id = max([int(v) for v in root.xpath(".//w:bookmarkStart/@w:id", namespaces=NS) if str(v).isdigit()] + [0]) + 1

    def add(text, role, before=None):
        nonlocal next_id
        p = _paragraph(text)
        _set_role(p, role, rules, width_pt)
        _mark(p, role + "_" + str(next_id), next_id)
        next_id += 1
        body.insert(list(body).index(before if before is not None else section), p)
        nodes.setdefault(role, []).append(p)
        changes.append({"operation": "insert_confirmed_metadata", "role": role, "text": text})
        return p

    if request["scope"] == "full":
        title = nodes["title"][0]
        if not nodes.get("issuing_authority"):
            authority = metadata["issuing_authority"]
            add(authority if authority.endswith("文件") else authority + "文件", "issuing_authority", title)
        if not nodes.get("document_number"):
            add(metadata["document_number"], "document_number", title)
        document_number = nodes["document_number"][0]
        if request["direction"] == "up":
            if not nodes.get("signatory"):
                # A right aligned tab keeps the confirmed signatory on the same line.
                run = ET.SubElement(document_number, W + "r")
                ET.SubElement(run, W + "tab")
                run = ET.SubElement(document_number, W + "r")
                signatory = re.sub(r"^签发人[：:]\s*", "", metadata["signatory"])
                ET.SubElement(run, W + "t").text = "签发人："
                name_run = ET.SubElement(document_number, W + "r")
                ET.SubElement(name_run, W + "t").text = signatory
                _set_format(document_number, rules["document_number"])
                name_fonts = _ensure(_ensure(name_run, "rPr"), "rFonts")
                name_fonts.set(W + "eastAsia", request["fonts"]["heading2"])
                name_fonts.set(W + "ascii", request["fonts"]["heading2"])
                name_fonts.set(W + "hAnsi", request["fonts"]["heading2"])
                tabs = _ensure(_ensure(document_number, "pPr"), "tabs")
                ET.SubElement(tabs, W + "tab", {W + "val": "right", W + "pos": str(round(156 / 25.4 * 1440 - 320))})
                # The inserted run is explicitly approved metadata, recorded for audit.
                _mark(run.getparent(), "signatory_inline", next_id)
                next_id += 1
                changes.append({"operation": "insert_confirmed_metadata", "role": "signatory", "text": signatory})
            else:
                # Existing separate signatory retains original text and its own row.
                changes.append({"operation": "preserve_source_signatory_row"})
        _border(document_number, "bottom", "FF0000", 8, 11)
        # Title is two line spaces after the red rule via the document-number paragraph.
        closing_candidates = nodes.get("attachment_label", []) + nodes.get("copy_to", []) + nodes.get("print_line", []) + [section]
        attachment = min(closing_candidates, key=lambda node: list(body).index(node))
        if not nodes.get("signature"):
            add(metadata["issuing_authority"], "signature", nodes.get("date", [attachment])[0])
        if not nodes.get("date"):
            following = nodes["signature"][0].getnext()
            add(metadata["date"], "date", following if following is not None else attachment)
        if metadata.get("copy_to") and not nodes.get("copy_to"):
            add(metadata["copy_to"] if metadata["copy_to"].startswith("抄送") else "抄送：" + metadata["copy_to"], "copy_to")
        if not nodes.get("print_line"):
            printer = add(metadata["print_authority"] + metadata["print_date"] + "印发", "print_line")
            printer.find("w:r/w:t", NS).text = metadata["print_authority"]
            run = ET.SubElement(printer, W + "r")
            ET.SubElement(run, W + "tab")
            run = ET.SubElement(printer, W + "r")
            ET.SubElement(run, W + "t").text = metadata["print_date"] + "印发"
            _set_format(printer, rules["print_line"])
            tabs = _ensure(_ensure(printer, "pPr"), "tabs")
            ET.SubElement(tabs, W + "tab", {W + "val": "right", W + "pos": str(round(156 / 25.4 * 1440 - 280))})
        imprint_nodes = nodes.get("copy_to", []) + nodes.get("print_line", [])
        first_imprint = imprint_nodes[0]
        top_line = add("", "imprint_top", first_imprint)
        bottom_line = add("", "imprint_bottom")
        middle_line = add("", "imprint_middle", nodes["print_line"][0]) if nodes.get("copy_to") else None
        for p in [top_line, bottom_line] + ([middle_line] if middle_line is not None else []):
            _set_format(p, {"size_pt": 1, "first_line_pt": 0, "left_indent_pt": 1.5, "right_indent_pt": 1.5,
                            "space_before_pt": 0, "space_after_pt": 0, "line_spacing_rule": "exact", "line_spacing_pt": 1})
            _ensure(_ensure(p, "pPr"), "adjustRightInd").set(W + "val", "0")
        imprint_nodes = [top_line] + nodes.get("copy_to", []) + ([middle_line] if middle_line is not None else []) + nodes.get("print_line", []) + [bottom_line]
        # A single nonrepeating text-frame anchored to the last imprint paragraph
        # puts the imprint at the bottom of the last text margin. Word layout is
        # checked separately; this is not a repeating header/footer.
        anchor = imprint_nodes[-1]
        for p in imprint_nodes:
            prop = _ensure(p, "pPr")
            frame = _ensure(prop, "framePr")
            for key, value in {"hAnchor": "margin", "vAnchor": "margin", "xAlign": "left", "yAlign": "bottom", "w": str(round(156 / 25.4 * 1440)), "wrap": "around", "hRule": "auto"}.items():
                frame.set(W + key, value)
            _ensure(prop, "keepLines").set(W + "val", "1")
            if p is not anchor:
                _ensure(prop, "keepNext").set(W + "val", "1")
        _border(imprint_nodes[0], "top", size=8)
        _border(imprint_nodes[-1], "bottom", size=8)
        if middle_line is not None:
            _border(middle_line, "top", size=6)
    parts["word/document.xml"] = ET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    _package_write(parts, output)
    audit = audit_official(source, output, request, plan["roles"])
    if audit["content"]["status"] != "PASS":
        output.unlink()
        raise ValueError("Official content preservation audit failed; output removed")
    from .fonts import check_fonts
    fonts = check_fonts(official_profile(request, plan["template"]))
    return {"output": str(output), "changes": changes, "audit": audit, "fonts": fonts,
            "layout": {"status": "UNVERIFIED", "reason": "Actual renderer pagination and visual review are required."},
            "template_differences": plan["template"].get("differences", [])}


def _strip_format(root):
    """Normalize only the format properties this module can modify."""
    pkeys = {"jc", "spacing", "ind", "keepNext", "keepLines", "snapToGrid", "pageBreakBefore", "pBdr", "framePr", "tabs", "adjustRightInd"}
    rkeys = {"rFonts", "sz", "szCs", "b", "i", "color", "spacing"}
    skeys = {"pgMar", "cols", "pgSz", "docGrid", "footerReference", "titlePg"}
    for node in root.findall(".//w:pPr", NS):
        for child in list(node):
            if ET.QName(child).localname in pkeys:
                node.remove(child)
    for node in root.findall(".//w:rPr", NS):
        for child in list(node):
            if ET.QName(child).localname in rkeys:
                node.remove(child)
    for node in root.findall(".//w:sectPr", NS):
        for child in list(node):
            if ET.QName(child).localname in skeys:
                node.remove(child)
            elif child.tag == W + "pgNumType":
                child.attrib.pop(W + "start", None)
    for tag in ("rPr", "pPr", "pgNumType", "sectPr"):
        for node in reversed(root.findall(".//w:" + tag, NS)):
            if not len(node) and not node.attrib:
                node.getparent().remove(node)
    return _canonical(root)


def audit_official(before, after, request=None, roles=None):
    request = _request(request)
    source_parts, output_parts = _package(before), _package(after)
    original = _xml(source_parts["word/document.xml"])
    result = _xml(output_parts["word/document.xml"])
    original_blocks = _inspect(before, request, roles)["blocks"]
    # Rebuild the expected result once from the authoritative source and request
    # would recurse. Instead remove only additions whose exact approved text and
    # native bookmark identify their semantic role, then compare original XML.
    metadata = _resolved_metadata({"blocks": original_blocks}, request)
    permitted = {"issuing_authority": {metadata.get("issuing_authority"), (metadata.get("issuing_authority") or "") + "文件"},
                 "document_number": {metadata.get("document_number")}, "signature": {metadata.get("issuing_authority")},
                 "date": {metadata.get("date")}, "copy_to": {metadata.get("copy_to"), "抄送：" + (metadata.get("copy_to") or "")},
                 "print_line": {(metadata.get("print_authority") or "") + (metadata.get("print_date") or "") + "印发"},
                 "imprint_top": {""}, "imprint_bottom": {""}, "imprint_middle": {""}}
    content_issues = []
    for p in list(result.findall(".//w:body//w:p", NS)):
        marks = p.xpath(".//w:bookmarkStart[starts-with(@w:name, '_MWOFF_')]/@w:name", namespaces=NS)
        if not marks:
            continue
        if any(name == _MANAGED + "signatory_inline" for name in marks):
            # Only the final appended tab and signatory run may be removed.
            runs = p.findall("w:r", NS)
            wanted = metadata.get("signatory") or ""
            expected = wanted if wanted.startswith("签发人") else "签发人：" + wanted
            if len(runs) < 3 or _text(runs[-2]) + _text(runs[-1]) != expected or not runs[-3].findall("w:tab", NS):
                content_issues.append("Unexpected inline signatory payload")
            else:
                p.remove(runs[-1])
                p.remove(runs[-2])
                p.remove(runs[-3])
            # A generated document-number paragraph can also carry this marker.
            for mark in list(p.findall("w:bookmarkStart", NS)):
                if mark.get(W + "name") == _MANAGED + "signatory_inline":
                    ident = mark.get(W + "id")
                    p.remove(mark)
                    for end in list(p.findall("w:bookmarkEnd", NS)):
                        if end.get(W + "id") == ident:
                            p.remove(end)
        names = p.xpath(".//w:bookmarkStart[starts-with(@w:name, '_MWOFF_')]/@w:name", namespaces=NS)
        if not names:
            continue
        name = names[0][len(_MANAGED):]
        role = re.sub(r"_\d+$", "", name)
        if request["scope"] != "full" or role not in permitted or _text(p) not in permitted[role]:
            content_issues.append("Unexpected generated paragraph: " + role)
        p.getparent().remove(p)
    if _strip_format(copy.deepcopy(original)) != _strip_format(copy.deepcopy(result)):
        content_issues.append("Original document content or native object structure changed")
    mutable = {"word/document.xml", "word/settings.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"}
    for name, data in source_parts.items():
        if name not in mutable and output_parts.get(name) != data:
            content_issues.append("Original package part changed: " + name)
    for name in set(output_parts) - set(source_parts):
        if name not in mutable and not re.fullmatch(r"word/mwOfficialFooter\d+\.xml", name):
            content_issues.append("Unexpected added package part: " + name)
    for name in mutable - {"word/document.xml"}:
        left = _xml(source_parts[name]) if name in source_parts else None
        right = _xml(output_parts[name]) if name in output_parts else None
        if right is None:
            content_issues.append("Missing package part: " + name)
            continue
        for item in list(right):
            if name == "word/settings.xml" and item.tag in {W + "evenAndOddHeaders", W + "updateFields"}:
                right.remove(item)
            elif name.endswith(".rels") and (item.get("Target") or "").startswith("mwOfficialFooter"):
                right.remove(item)
            elif name == "[Content_Types].xml" and (item.get("PartName") or "").startswith("/word/mwOfficialFooter"):
                right.remove(item)
        if left is not None:
            for item in list(left):
                if name == "word/settings.xml" and item.tag in {W + "evenAndOddHeaders", W + "updateFields"}:
                    left.remove(item)
            if _canonical(left) != _canonical(right):
                content_issues.append("Unexpected package metadata change: " + name)
    # Audit format values against source role mapping, excluding explicit additions.
    output_root = _xml(output_parts["word/document.xml"])
    output_paragraphs = [p for p in output_root.findall(".//w:body//w:p", NS) if not _managed(p)]
    if request["direction"] == "up":
        # An original paragraph with an inline metadata marker remains a source block.
        output_paragraphs = [p for p in output_root.findall(".//w:body//w:p", NS)
                             if not _managed(p) or p.xpath(".//w:bookmarkStart[@w:name='_MWOFF_signatory_inline']", namespaces=NS)
                             and not any(re.match(r"_MWOFF_document_number_\d+$", x) for x in p.xpath(".//w:bookmarkStart/@w:name", namespaces=NS))]
    rules = _rules(request)
    _signature_rules(rules, metadata, request)
    if request["mode"] == "template":
        for role, props in _learn_template(request)["rules"].items():
            _merge_rule(rules[role], props)
    styles = _Styles(output_parts)
    style_issues = []
    expected_page = {**PAGE, **(_learn_template(request).get("page", {}) if request["mode"] == "template" else {})}
    width_pt = (expected_page["width_mm"] - expected_page["margin_left_mm"] - expected_page["margin_right_mm"]) / 25.4 * 72
    for block, p in zip(original_blocks, output_paragraphs):
        for key, expected in _block_rule(block["role"], block["text"], rules, width_pt).items():
            actual = styles.effective(p).get(key)
            equal = abs(actual - expected) < 0.11 if isinstance(actual, (int, float)) and isinstance(expected, (int, float)) else actual == expected or key == "alignment" and {actual, expected} <= {"both", "justify"}
            if not equal:
                style_issues.append({"id": block["id"], "property": key, "expected": expected, "actual": actual})
    for p in output_root.findall(".//w:body//w:p", NS):
        names = p.xpath(".//w:bookmarkStart/@w:name", namespaces=NS)
        for name in names:
            match = re.fullmatch(r"_MWOFF_(.+)_\d+", name)
            if not match or match.group(1) not in rules:
                continue
            role = match.group(1)
            actual = styles.effective(p)
            for key, expected in _block_rule(role, _text(p), rules, width_pt).items():
                observed = actual.get(key)
                equal = abs(observed - expected) < 0.11 if isinstance(observed, (int, float)) and isinstance(expected, (int, float)) else observed == expected or key == "alignment" and {observed, expected} <= {"both", "justify"}
                if not equal:
                    style_issues.append({"id": name, "property": key, "expected": expected, "actual": observed})
        if _MANAGED + "signatory_inline" in names:
            name_runs = [r for r in p.findall("w:r", NS) if _text(r) == re.sub(r"^签发人[：:]\s*", "", metadata.get("signatory") or "")]
            if not name_runs or any(r.find("w:rPr/w:rFonts", NS) is None or r.find("w:rPr/w:rFonts", NS).get(W + "eastAsia") != request["fonts"]["heading2"] for r in name_runs):
                style_issues.append({"id": "signatory_inline", "property": "east_asia_font", "expected": request["fonts"]["heading2"]})
    footers = [name for name in output_parts if re.fullmatch(r"word/mwOfficialFooter\d+\.xml", name)]
    structure_issues = []
    if len(footers) != 2:
        structure_issues.append("Expected dedicated odd and even page-number footers")
    for name in footers:
        footer = _xml(output_parts[name])
        if len(footer.xpath(".//w:fldSimple[normalize-space(@w:instr)='PAGE']", namespaces=NS)) != 1:
            structure_issues.append("Missing native PAGE field: " + name)
    from .word import _page
    sections = output_root.findall(".//w:sectPr", NS)
    if len(sections) != 1:
        structure_issues.append("Official layout must contain one supported section")
    for section in sections:
        actual_page = _page(section)
        for key, expected in expected_page.items():
            actual = actual_page.get(key)
            equal = abs(actual - expected) < 0.11 if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) else actual == expected
            if not equal:
                structure_issues.append({"property": key, "expected": expected, "actual": actual})
        grid = _child(section, "docGrid")
        expected_chars = _character_grid(source_parts, expected_page)
        if grid is None or grid.get(W + "charSpace") != expected_chars:
            structure_issues.append("Official character grid is missing or differs from planned grid")
        footer_refs = {n.get(W + "type"): n.get(R + "id") for n in section.findall("w:footerReference", NS)}
        rels = _xml(output_parts["word/_rels/document.xml.rels"])
        rel_targets = {n.get("Id"): n.get("Target") for n in rels}
        for kind, align in (("default", "right"), ("even", "left")):
            target = rel_targets.get(footer_refs.get(kind))
            if not target or "word/" + target not in output_parts:
                structure_issues.append("Missing " + kind + " page-number relationship")
                continue
            footer = _xml(output_parts["word/" + target])
            p = footer.find("w:p", NS)
            actual = _Styles(output_parts).effective(p) if p is not None else {}
            if actual.get("alignment") != align or actual.get("size_pt") != 14 or actual.get("east_asia_font") != request["fonts"]["page_number"]:
                structure_issues.append("Wrong " + kind + " page-number position, size or font")
            if _text(footer) != "— 1 —":
                structure_issues.append("Page-number ornament or cache was changed: " + kind)
    for block, p in zip(original_blocks, output_paragraphs):
        if block["role"] == "attachment_label":
            flag = p.find("w:pPr/w:pageBreakBefore", NS)
            if flag is None or flag.get(W + "val", "1") in {"0", "false", "off"}:
                structure_issues.append("Attachment must start on a new page: " + block["id"])
    settings = _xml(output_parts["word/settings.xml"])
    odd_even = _child(settings, "evenAndOddHeaders")
    if odd_even is None or odd_even.get(W + "val", "1") in {"0", "false", "off"}:
        structure_issues.append("Odd/even page-number setting is missing")
    if request["scope"] == "full":
        frames = output_root.findall(".//w:framePr", NS)
        if not frames or any(frame.get(W + "yAlign") != "bottom" or frame.get(W + "vAnchor") != "margin" for frame in frames):
            structure_issues.append("Missing or misplaced nonrepeating last-page imprint frame")
        red_borders = output_root.xpath(".//w:pBdr/w:bottom[@w:color='FF0000']", namespaces=NS)
        if not red_borders:
            structure_issues.append("Missing official red separator")
        markers = output_root.xpath(".//w:bookmarkStart/@w:name", namespaces=NS)
        source_roles = {b["role"] for b in original_blocks}
        for role in ("issuing_authority", "document_number", "signature", "date", "print_line"):
            if role not in source_roles and not any(re.match(re.escape(_MANAGED + role) + r"_\d+$", name) for name in markers):
                structure_issues.append("Missing full-layout element: " + role)
    return {"status": "FAIL" if content_issues or style_issues or structure_issues else "UNVERIFIED",
            "content": {"status": "FAIL" if content_issues else "PASS", "issues": content_issues},
            "style": {"status": "FAIL" if style_issues else "PASS", "issues": style_issues},
            "structure": {"status": "FAIL" if structure_issues else "PASS", "issues": structure_issues},
            "visual": {"status": "UNVERIFIED", "reason": "Renderer output and page review required."}}


def _word_measure(source):
    """Read actual Word pagination for the last-page imprint and source blocks.

    This read-only measurement never claims visual acceptance and does not save
    Word's rewritten OOXML over the content-preserving package.
    """
    import os
    if os.name != "nt":
        return {"status": "UNVERIFIED", "reason": "Word pagination measurement is available on Windows."}
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return {"status": "UNVERIFIED", "reason": "Word automation is unavailable."}
    pythoncom.CoInitialize()
    app = document = None
    try:
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        app.AutomationSecurity = 3
        app.Options.UpdateLinksAtOpen = False
        document = app.Documents.Open(str(Path(source).resolve()), ConfirmConversions=False, ReadOnly=True,
                                      AddToRecentFiles=False, Visible=False, OpenAndRepair=False)
        document.Repaginate()
        pages = document.ComputeStatistics(2)
        measured = []
        for paragraph in document.Paragraphs:
            value = paragraph.Range.Text.rstrip("\r\x07")
            if not value.strip():
                continue
            measured.append({"text": value, "page": paragraph.Range.Information(3),
                             "x_pt": paragraph.Range.Information(5), "y_pt": paragraph.Range.Information(6)})
        imprint = [p for p in measured if p["text"].startswith("抄送") or re.search(r"\d{4}年\d{1,2}月\d{1,2}日印发$", p["text"])]
        issues = []
        if imprint and any(p["page"] != pages for p in imprint):
            issues.append("Imprint is not on the last rendered page")
        return {"status": "FAIL" if issues else "PASS", "renderer": "word", "pages": pages,
                "paragraphs": measured, "issues": issues, "visual": "UNVERIFIED",
                "scope": "Actual pagination and imprint page; line geometry, fonts and overlaps still require rendered checks."}
    except Exception as error:
        return {"status": "UNVERIFIED", "reason": str(error)}
    finally:
        if document is not None:
            document.Close(False)
        if app is not None:
            app.Quit(False)
        pythoncom.CoUninitialize()


def finalize_layout(source, output=None):
    """Measure Word layout in an isolated process; never save over the DOCX."""
    import importlib.util
    import json
    import os
    import subprocess
    import sys

    from .render import word_render_risk
    risk = word_render_risk(source)
    if risk:
        return {"status": "UNVERIFIED", "reason": risk}
    if os.name != "nt" or importlib.util.find_spec("win32com") is None:
        return {"status": "UNVERIFIED", "reason": "Microsoft Word automation is unavailable."}
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    environment["PYTHONIOENCODING"] = "utf-8"
    code = "import json,sys; from manuweave.official import _word_measure; print(json.dumps(_word_measure(sys.argv[1]), ensure_ascii=False))"
    try:
        process = subprocess.run([sys.executable, "-c", code, str(Path(source).resolve())],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace",
                                 env=environment, timeout=90)
        if process.returncode:
            report = {"status": "UNVERIFIED", "reason": "Word layout measurement failed", "diagnostic": process.stderr[-2000:]}
        else:
            report = json.loads(process.stdout)
    except subprocess.TimeoutExpired:
        report = {"status": "UNVERIFIED", "reason": "Word layout measurement exceeded 90 seconds"}
    except (ValueError, OSError) as error:
        report = {"status": "UNVERIFIED", "reason": str(error)}
    if output is not None:
        from .io import write_json
        if Path(output).exists():
            raise FileExistsError("Layout measurement report already exists")
        write_json(output, report)
    return report
