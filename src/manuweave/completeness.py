"""Evidence-constrained structural completion; never supplies missing research facts."""
from __future__ import annotations

import hashlib
import copy
import json
import re
import posixpath
import zipfile
from pathlib import Path
from typing import Literal

from lxml import etree
from pydantic import BaseModel, ConfigDict, Field

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    block_id: str
    quote: str = Field(min_length=1, max_length=20000)


class Draft(StrictModel):
    role: Literal["abstract", "keywords", "conclusion", "caption"]
    text: str = Field(min_length=1, max_length=40000)
    evidence: list[Evidence] = Field(min_length=1, max_length=100)


class Caption(StrictModel):
    block_id: str
    text: str = Field(min_length=1, max_length=5000)
    kind: Literal["figure", "table"]


class CompletionRequest(StrictModel):
    enabled_content: bool = False
    add_toc: bool = False
    add_page_numbers: bool = False
    number_headings: bool = False
    captions: list[Caption] = Field(default_factory=list, max_length=1000)
    drafts: list[Draft] = Field(default_factory=list, max_length=100)


def analyze_missing(ir: dict) -> dict:
    """Return actionable categories, without guessing research-specific requirements."""
    blocks = ir.get("blocks", []) + ir.get("object_blocks", [])
    roles = {b.get("role") for b in blocks}
    texts = "\n".join(b.get("text", "") for b in blocks)
    issues = []

    def issue(key, category, detail, action, ids=None):
        issues.append({"id": key, "category": category, "detail": detail,
                       "action": action, "block_ids": ids or []})

    has_abstract = any(b.get("role") == "abstract" and re.sub(r"^\s*(?:摘要|abstract)\s*[:：]?\s*", "", b.get("text", ""), flags=re.I).strip() for b in blocks)
    if not has_abstract:
        issue("missing_abstract", "evidence_draft", "No abstract detected.",
              "Host may propose an evidence-linked abstract in explicit content mode.")
    has_keywords = any(b.get("role") == "keywords" and re.sub(r"^\s*(?:关键词|关键字|key\s*words)\s*[:：]?\s*", "", b.get("text", ""), flags=re.I).strip() for b in blocks)
    if not has_keywords:
        issue("missing_keywords", "evidence_draft", "No keywords detected.",
              "Host may select verbatim terms from cited source blocks.")
    has_headings = any(str(role).startswith("heading") for role in roles)
    if has_headings and "toc" not in roles and not re.search(r"TOC\s+|目录|contents", texts, re.I):
        issue("missing_toc", "safe_auto", "Headings exist, but no table of contents was detected.",
              "Insert a native TOC field; renderer must refresh page numbers.")
    for kind in ("figure", "table"):
        object_roles = {"figure", "image", "legacy_image"} if kind == "figure" else {"table"}
        native_objects = [b for b in ir.get("object_blocks", [])
                          if b.get("role") in object_roles or b.get("kind") == kind]
        objects = native_objects or [b for b in ir.get("blocks", [])
                                     if b.get("role") in object_roles or b.get("kind") == kind]
        captions = [b for b in blocks if b.get("role") in {"caption", "figure_caption", "table_caption"} and
                    re.match(r"\s*(图|Figure|Fig\.)" if kind == "figure" else r"\s*(表|Table)",
                             b.get("text", ""), re.I)]
        for obj in objects[len(captions):]:
            issue("missing_caption_" + str(obj.get("id")), "evidence_draft",
                  f"A {kind} may lack a caption; association requires review.",
                  "Supply a caption grounded in the object and source text; assign its sequence automatically.",
                  [obj.get("id")])
    if "reference" not in roles and "bibliography" not in roles:
        issue("missing_references", "needs_user", "No bibliography detected; requirement depends on document scope.",
              "Request real sources; never invent bibliographic entries.")
    if not re.search(r"实验|数据|方法|experiment|dataset|method", texts, re.I):
        issue("research_evidence_unconfirmed", "needs_user",
              "No obvious methods or data description detected; this is a heuristic, not proof of absence.",
              "Ask for methods and results if the manuscript makes empirical claims.")
    return {"issues": issues, "counts": {c: sum(i["category"] == c for i in issues)
                                         for c in ("safe_auto", "evidence_draft", "needs_user")},
            "status": "UNKNOWN" if issues else "PASS",
            "limitations": ["Heading and caption detection is heuristic; document genre controls requirements."]}


def _xml(data: bytes):
    return etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))


def _paragraph(text: str, role: str | None = None):
    p = etree.Element(f"{{{W}}}p")
    if role:
        prop = etree.SubElement(p, f"{{{W}}}pPr")
        etree.SubElement(prop, f"{{{W}}}pStyle").set(f"{{{W}}}val", role)
    r = etree.SubElement(p, f"{{{W}}}r")
    etree.SubElement(r, f"{{{W}}}t").text = text
    return p


def _numbering(parts: dict[str, bytes]) -> str:
    numbering = _xml(parts["word/numbering.xml"]) if "word/numbering.xml" in parts else etree.Element(f"{{{W}}}numbering", nsmap={"w": W})
    ids = [int(x) for x in numbering.xpath("//@w:abstractNumId | //@w:numId", namespaces=NS) if str(x).isdigit()]
    next_id = str(max(ids, default=0) + 1)
    abstract = etree.Element(f"{{{W}}}abstractNum", {f"{{{W}}}abstractNumId": next_id})
    first_num = numbering.find(f"{{{W}}}num")
    if first_num is None:
        numbering.append(abstract)
    else:
        first_num.addprevious(abstract)
    etree.SubElement(abstract, f"{{{W}}}multiLevelType", {f"{{{W}}}val": "multilevel"})
    for level in range(9):
        node = etree.SubElement(abstract, f"{{{W}}}lvl", {f"{{{W}}}ilvl": str(level)})
        for tag, value in (("start", "1"), ("numFmt", "decimal"),
                           ("lvlText", ".".join("%" + str(i + 1) for i in range(level + 1))),
                           ("lvlJc", "left")):
            etree.SubElement(node, f"{{{W}}}{tag}", {f"{{{W}}}val": value})
    num = etree.SubElement(numbering, f"{{{W}}}num", {f"{{{W}}}numId": next_id})
    etree.SubElement(num, f"{{{W}}}abstractNumId", {f"{{{W}}}val": next_id})
    parts["word/numbering.xml"] = etree.tostring(numbering, xml_declaration=True, encoding="UTF-8")
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    relpath = "word/_rels/document.xml.rels"
    rels = _xml(parts[relpath]) if relpath in parts else etree.Element(f"{{{rel_ns}}}Relationships")
    if not any(e.get("Type", "").endswith("/numbering") for e in rels):
        used = {e.get("Id") for e in rels}
        index = 1
        while f"rIdManuWeave{index}" in used:
            index += 1
        etree.SubElement(rels, f"{{{rel_ns}}}Relationship", Id=f"rIdManuWeave{index}",
                         Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering",
                         Target="numbering.xml")
    parts[relpath] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8")
    content = _xml(parts["[Content_Types].xml"])
    if not any(e.get("PartName") == "/word/numbering.xml" for e in content):
        etree.SubElement(content, "{http://schemas.openxmlformats.org/package/2006/content-types}Override",
                         PartName="/word/numbering.xml",
                         ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml")
    parts["[Content_Types].xml"] = etree.tostring(content, xml_declaration=True, encoding="UTF-8")
    return next_id




def _add_page_numbers(parts, document_root):
    """Attach native PAGE fields to default and already declared footer variants."""
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    relpath = "word/_rels/document.xml.rels"
    rels = _xml(parts[relpath]) if relpath in parts else etree.Element(f"{{{rel_ns}}}Relationships")
    content = _xml(parts["[Content_Types].xml"])
    footer_type = office_rel + "/footer"
    by_id = {element.get("Id"): element for element in rels}
    current_default = None
    modified = set()
    changes = []
    sections = document_root.findall(".//w:sectPr", NS)
    if not sections:
        section = etree.SubElement(document_root.find("w:body", NS), f"{{{W}}}sectPr")
        sections = [section]

    def footer_path(relation_id):
        relation = by_id.get(relation_id)
        if relation is None or relation.get("Type") != footer_type or relation.get("TargetMode") == "External":
            raise ValueError("Footer must reference an internal footer relationship")
        target = relation.get("Target", "")
        path = posixpath.normpath("word/" + target) if not target.startswith("/") else target.lstrip("/")
        if not path.startswith("word/") or "\\" in path or ":" in path or path not in parts:
            raise ValueError("Footer relationship escapes the supported package scope or is missing")
        if _xml(parts[path]).tag != f"{{{W}}}ftr":
            raise ValueError("Footer relationship does not point to a footer XML part")
        return path

    def new_footer():
        number = 1
        while f"word/footer{number}.xml" in parts:
            number += 1
        path = f"word/footer{number}.xml"
        parts[path] = etree.tostring(etree.Element(f"{{{W}}}ftr", nsmap={"w": W}), xml_declaration=True, encoding="UTF-8")
        index = 1
        while f"rIdManuWeaveFooter{index}" in by_id:
            index += 1
        relation_id = f"rIdManuWeaveFooter{index}"
        relation = etree.SubElement(rels, f"{{{rel_ns}}}Relationship", Id=relation_id, Type=footer_type,
                                    Target=f"footer{number}.xml")
        by_id[relation_id] = relation
        etree.SubElement(content, "{http://schemas.openxmlformats.org/package/2006/content-types}Override",
                         PartName="/" + path, ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml")
        changes.append({"operation": "create_footer", "part": path})
        return relation_id

    def add_reference(section, relation_id):
        ref = etree.Element(f"{{{W}}}footerReference", {f"{{{W}}}type": "default", f"{{{office_rel}}}id": relation_id})
        predecessors = [child for child in section if child.tag in {f"{{{W}}}headerReference", f"{{{W}}}footerReference"}]
        if predecessors:
            predecessors[-1].addnext(ref)
        else:
            section.insert(0, ref)

    all_footer_ids = []
    for index, section in enumerate(sections):
        default = next((ref for ref in section.findall("w:footerReference", NS)
                        if ref.get(f"{{{W}}}type", "default") == "default"), None)
        if default is not None:
            current_default = default.get(f"{{{office_rel}}}id")
            footer_path(current_default)
        else:
            if current_default is None:
                current_default = new_footer()
            add_reference(section, current_default)
            changes.append({"operation": "link_page_number_footer", "section": index,
                            "relationship_id": current_default})
        all_footer_ids.extend(ref.get(f"{{{office_rel}}}id") for ref in section.findall("w:footerReference", NS))
    for relation_id in dict.fromkeys(all_footer_ids):
        path = footer_path(relation_id)
        footer = _xml(parts[path])
        has_page = any(re.search(r"(?:^|\s)PAGE(?:\s|$)", value, re.I) for value in footer.xpath(".//w:instrText/text() | .//w:fldSimple/@w:instr", namespaces=NS))
        if has_page:
            continue
        paragraph = etree.SubElement(footer, f"{{{W}}}p")
        prop = etree.SubElement(paragraph, f"{{{W}}}pPr")
        etree.SubElement(prop, f"{{{W}}}jc", {f"{{{W}}}val": "center"})
        field = etree.SubElement(paragraph, f"{{{W}}}fldSimple", {f"{{{W}}}instr": " PAGE ", f"{{{W}}}dirty": "true"})
        run = etree.SubElement(field, f"{{{W}}}r")
        etree.SubElement(run, f"{{{W}}}t").text = "1"
        parts[path] = etree.tostring(footer, xml_declaration=True, encoding="UTF-8", standalone=True)
        modified.add(path)
        changes.append({"operation": "insert_page_field", "part": path, "requires_field_refresh": True})
    # Preserve byte stability when an existing relationship or content-types part needs no addition.
    if any(change["operation"] == "create_footer" for change in changes):
        parts[relpath] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8")
        parts["[Content_Types].xml"] = etree.tostring(content, xml_declaration=True, encoding="UTF-8")
    return modified, changes

def _content_audit(original_parts, final_parts, original_nodes, document_root, authorized_footers=None):
    """Check original nodes in place while separately allowing logged insertions."""
    checks = []
    for kind, xpath in (
        ("equations", ".//m:oMath"),
        ("images", ".//w:drawing | .//w:pict"),
        ("tables", ".//w:tbl"),
    ):
        namespaces = {**NS, "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
        before = _xml(original_parts["word/document.xml"]).xpath(xpath, namespaces=namespaces)
        after = _xml(final_parts["word/document.xml"]).xpath(xpath, namespaces=namespaces)
        checks.append({"name": kind, "status": "PASS" if
                       [etree.tostring(e, method="c14n", exclusive=True) for e in before] ==
                       [etree.tostring(e, method="c14n", exclusive=True) for e in after] else "FAIL"})
    original_content_ok = True
    live_paragraphs = set(document_root.xpath(".//w:body//w:p", namespaces=NS))
    for node, signature in original_nodes:
        if node not in live_paragraphs:
            original_content_ok = False
        current = copy.deepcopy(node)
        if current.tag == f"{{{W}}}p":
            prop = current.find("w:pPr", NS)
            if prop is not None:
                current.remove(prop)
        if etree.tostring(current, method="c14n", exclusive=True) != signature:
            original_content_ok = False
    checks.append({"name": "original_content_nodes", "status": "PASS" if original_content_ok else "FAIL"})
    authorized_footers = authorized_footers or set()
    footer_content_ok = True
    for name in authorized_footers:
        if name in original_parts:
            old_children = list(_xml(original_parts[name]))
            new_children = list(_xml(final_parts[name]))
            if len(new_children) < len(old_children) or any(etree.tostring(old, method="c14n", exclusive=True) != etree.tostring(new, method="c14n", exclusive=True)
                   for old, new in zip(old_children, new_children)):
                footer_content_ok = False
    checks.append({"name": "existing_footer_content", "status": "PASS" if footer_content_ok else "FAIL"})
    relationships_ok = True
    for name in ("word/_rels/document.xml.rels", "[Content_Types].xml"):
        if name in original_parts:
            after_entries = [dict(child.attrib) for child in _xml(final_parts[name])]
            if any(dict(child.attrib) not in after_entries for child in _xml(original_parts[name])):
                relationships_ok = False
    checks.append({"name": "existing_relationships_and_content_types", "status": "PASS" if relationships_ok else "FAIL"})
    before_sections = _xml(original_parts["word/document.xml"]).findall(".//w:sectPr", NS)
    after_sections = _xml(final_parts["word/document.xml"]).findall(".//w:sectPr", NS)
    sections_ok = len(before_sections) == len(after_sections) or not before_sections
    for before_section, after_section in zip(before_sections, after_sections):
        old_refs = [dict(child.attrib) for child in before_section.findall("w:footerReference", NS)]
        new_refs = [dict(child.attrib) for child in after_section.findall("w:footerReference", NS)]
        if any(ref not in new_refs for ref in old_refs):
            sections_ok = False
        for section in (before_section, after_section):
            for ref in section.findall("w:footerReference", NS):
                section.remove(ref)
        if etree.tostring(before_section, method="c14n", exclusive=True) != etree.tostring(after_section, method="c14n", exclusive=True):
            sections_ok = False
    checks.append({"name": "section_properties_and_existing_footer_references", "status": "PASS" if sections_ok else "FAIL"})
    mutable = {"word/document.xml", "word/numbering.xml", "word/_rels/document.xml.rels", "[Content_Types].xml"} | authorized_footers
    unchanged = all(final_parts.get(name) == data for name, data in original_parts.items() if name not in mutable)
    checks.append({"name": "media_footnotes_endnotes_and_other_parts", "status": "PASS" if unchanged else "FAIL"})
    return {"status": "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PASS", "checks": checks,
            "scope": "All original paragraph content, equations, image objects, tables, and non-editable package parts; authorized added nodes are separate."}

def apply_completion(source: Path, output: Path, request: dict) -> dict:
    """Apply authorized deterministic additions; retain non-extractive prose for review."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists():
        raise ValueError("Completion requires a new output path")
    if source.suffix.lower() != ".docx" or output.suffix.lower() != ".docx":
        raise ValueError("Completion currently supports DOCX only")
    req = CompletionRequest.model_validate(request)
    if req.drafts and not req.enabled_content:
        raise ValueError("Substantive completion requires enabled_content=true")
    from .word import _package
    if len({d.role for d in req.drafts}) != len(req.drafts):
        raise ValueError("Duplicate completion roles require a single consolidated draft")
    parts = _package(source)
    original_parts = dict(parts)
    root = _xml(parts["word/document.xml"])
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("DOCX body missing")
    from .word import inspect_docx
    ir = inspect_docx(source)
    blocks = {b["id"]: b for b in ir.get("blocks", []) + ir.get("object_blocks", [])}
    changes, pending = [], []
    original_paragraphs = list(root.xpath(".//w:body//w:p", namespaces=NS))
    original_nodes = []
    for node in original_paragraphs:
        clone = copy.deepcopy(node)
        prop = clone.find("w:pPr", NS)
        if prop is not None:
            clone.remove(prop)
        original_nodes.append((node, etree.tostring(clone, method="c14n", exclusive=True)))
    resolved_nodes = {}
    for block_id, block in blocks.items():
        source_map = block.get("source", {})
        if isinstance(source_map, dict) and source_map.get("xpath"):
            found = root.xpath(source_map["xpath"], namespaces=NS)
            if len(found) == 1:
                resolved_nodes[block_id] = found[0]
    # Source maps identify real XML nodes. Text matching is only an unambiguous fallback.
    def locate(block_id):
        if block_id not in blocks:
            raise ValueError(f"Unknown block: {block_id}")
        block = blocks[block_id]
        if block_id in resolved_nodes:
            return resolved_nodes[block_id]
        matches = [p for p in original_paragraphs if "".join(p.xpath(".//w:t/text()", namespaces=NS)) == block.get("text", "")]
        if len(matches) != 1:
            raise ValueError("Ambiguous source location; explicit source map required")
        return matches[0]

    front_ranks = {"title": 0, "abstract_heading": 1, "abstract": 1, "keywords": 2}
    front_nodes = {locate(b["id"]): front_ranks[b["role"]] for b in blocks.values()
                   if b.get("role") in front_ranks and locate(b["id"]).getparent() is body}
    def insert_front(node, rank):
        anchors = [child for child in body if child in front_nodes and front_nodes[child] <= rank]
        if anchors:
            anchors[-1].addnext(node)
        else:
            body.insert(0, node)
        front_nodes[node] = rank
    toc_to_insert = None
    heading_targets = [(b, locate(b["id"])) for b in blocks.values()
                       if re.fullmatch(r"heading[1-6]", b.get("role", ""))
                       and not locate(b["id"]).xpath('.//w:fldSimple[contains(@w:instr,"TOC")] | .//w:instrText[contains(.,"TOC")]', namespaces=NS)]
    if req.add_toc or req.number_headings:
        for block, node in heading_targets:
            prop = node.find("w:pPr", NS)
            if prop is None:
                prop = etree.Element(f"{{{W}}}pPr")
                node.insert(0, prop)
            level = prop.find("w:outlineLvl", NS)
            if level is None:
                level = etree.SubElement(prop, f"{{{W}}}outlineLvl")
            target_value = str(int(block["role"][-1]) - 1)
            if level.get(f"{{{W}}}val") != target_value:
                level.set(f"{{{W}}}val", target_value)
                changes.append({"operation": "set_heading_outline", "block_id": block["id"], "level": int(target_value)})
    if req.add_toc:
        if not root.xpath('.//w:instrText[contains(., "TOC")] | .//w:fldSimple[contains(@w:instr,"TOC")]', namespaces=NS):
            if not heading_targets:
                raise ValueError("Cannot insert a meaningful table of contents without headings")
            p = _paragraph("")
            p.remove(p[-1])
            field = etree.SubElement(p, f"{{{W}}}fldSimple", {f"{{{W}}}instr": ' TOC \\o "1-6" \\h \\z \\u ', f"{{{W}}}dirty": "true"})
            for index, (block, _) in enumerate(heading_targets):
                run = etree.SubElement(field, f"{{{W}}}r")
                if index:
                    etree.SubElement(run, f"{{{W}}}br")
                etree.SubElement(run, f"{{{W}}}t").text = block["text"]
            toc_to_insert = p
            changes.append({"operation": "insert_toc", "location": "word/document.xml", "requires_field_refresh": True,
                            "cached_entries": [b["text"] for b, _ in heading_targets], "page_numbers": "UNVERIFIED_UNTIL_FIELD_REFRESH"})
    if req.number_headings:
        targets = list(heading_targets)
        targets = [(b, p) for b, p in targets if not re.match(r"^\s*\d+[.、\s]", b.get("text", "")) and p.find("w:pPr/w:numPr", NS) is None]
        if targets:
            num_id = _numbering(parts)
            for b, p in targets:
                prop = p.find("w:pPr", NS)
                if prop is None:
                    prop = etree.Element(f"{{{W}}}pPr")
                    p.insert(0, prop)
                num = etree.SubElement(prop, f"{{{W}}}numPr")
                etree.SubElement(num, f"{{{W}}}ilvl", {f"{{{W}}}val": str(int(b["role"][-1]) - 1)})
                etree.SubElement(num, f"{{{W}}}numId", {f"{{{W}}}val": num_id})
                changes.append({"operation": "number_heading", "block_id": b["id"]})
    sequence = {"figure": 0, "table": 0}
    for b in blocks.values():
        for kind, pattern in (("figure", r"(?:图|Figure|Fig\.)\s*(\d+)"), ("table", r"(?:表|Table)\s*(\d+)")):
            match = re.match(pattern, b.get("text", ""), re.I)
            if b.get("role") in {"caption", "figure_caption", "table_caption"} and match:
                sequence[kind] = max(sequence[kind], int(match.group(1)))
    for caption in req.captions:
        target = locate(caption.block_id)
        if target.tag not in {f"{{{W}}}p", f"{{{W}}}tbl"}:
            ancestors = target.xpath("ancestor::w:p[1]", namespaces=NS)
            if not ancestors:
                raise ValueError("Caption object has no valid paragraph container")
            target = ancestors[0]
        if blocks[caption.block_id].get("role") not in {caption.kind, "image", "figure", "table", "body"}:
            raise ValueError("Caption target is not an object block")
        following = target.getnext()
        if following is not None:
            existing = "".join(following.xpath(".//w:t/text()", namespaces=NS))
            if re.fullmatch(r"(?:Figure|Table) \d+\. " + re.escape(caption.text), existing):
                continue
        sequence[caption.kind] += 1
        label = "Figure" if caption.kind == "figure" else "Table"
        text = f"{label} {sequence[caption.kind]}. {caption.text}"
        target.addnext(_paragraph(text, "Caption"))
        changes.append({"operation": "insert_caption", "block_id": caption.block_id, "text": text,
                        "basis": "explicit user-supplied caption"})
    for draft in sorted(req.drafts, key=lambda d: {"abstract": 0, "keywords": 1, "conclusion": 2, "caption": 3}[d.role]):
        quotes = []
        for ev in draft.evidence:
            if ev.block_id not in blocks or ev.quote not in blocks[ev.block_id].get("text", ""):
                raise ValueError("Evidence quote does not match its source block")
            quotes.append(ev.quote)
        # Only a verbatim excerpt or whitespace-joined excerpts enter the document.
        # Supporting arbitrary generated prose requires human semantic review.
        allowed = {q.strip() for q in quotes} | {" ".join(q.strip() for q in quotes), "\n".join(q.strip() for q in quotes)}
        protected = re.search(r"基金|伦理|批准|作者|funding|ethics|approval|author|\[[0-9]+\]", draft.text, re.I)
        if draft.text.strip() not in allowed or protected or draft.role == "caption":
            pending.append({**draft.model_dump(), "status": "AWAITING_REVIEW",
                            "reason": "Non-extractive or protected factual content requires human review."})
            continue
        labels = {"abstract": r"(?:摘要|abstract)", "keywords": r"(?:关键词|关键字|key\s*words)",
                  "conclusion": r"(?:结论|conclusion)", "caption": r"(?:图|表|caption)"}
        existing = [b for b in blocks.values() if b.get("role") == draft.role and
                    re.sub(r"^\s*" + labels[draft.role] + r"\s*[:：]?\s*", "", b.get("text", ""), flags=re.I).strip()]
        if existing:
            raise ValueError(f"Role {draft.role} already exists; completion will not replace it")
        label = {"abstract": "Abstract", "keywords": "Keywords", "conclusion": "Conclusion", "caption": "Caption"}[draft.role]
        empty_headings = [b for b in blocks.values() if b.get("role") in {draft.role, draft.role + "_heading"} and
                          not re.sub(r"^\s*" + labels[draft.role] + r"\s*[:：]?\s*", "", b.get("text", ""), flags=re.I).strip()]
        if empty_headings:
            p = _paragraph(draft.text)
            locate(empty_headings[0]["id"]).addnext(p)
            if draft.role in {"abstract", "keywords"}:
                front_nodes[p] = 1 if draft.role == "abstract" else 2
        else:
            p = _paragraph(f"{label}: {draft.text}")
            if draft.role in {"abstract", "keywords"}:
                insert_front(p, 1 if draft.role == "abstract" else 2)
            else:
                section = body.find("w:sectPr", NS)
                if section is not None:
                    section.addprevious(p)
                else:
                    body.append(p)
        changes.append({"operation": "insert_extractive_draft", "role": draft.role,
                        "text": draft.text, "evidence": [e.model_dump() for e in draft.evidence]})
    if toc_to_insert is not None:
        insert_front(toc_to_insert, 3)
    authorized_footers = set()
    if req.add_page_numbers:
        authorized_footers, page_changes = _add_page_numbers(parts, root)
        changes.extend(page_changes)
    parts["word/document.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    integrity = _content_audit(original_parts, parts, original_nodes, root, authorized_footers)
    if integrity["status"] != "PASS":
        raise ValueError("Completion integrity audit failed; no output written")
    output.parent.mkdir(parents=True, exist_ok=True)
    sidecar = output.with_suffix(output.suffix + ".completion.json")
    if sidecar.exists():
        raise ValueError("Completion report already exists")
    report = {"status": "UNKNOWN" if pending else "PASS", "changes": changes,
              "integrity": integrity, "pending_drafts": pending, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "output": str(output), "content_mode": req.enabled_content,
              "verification": "Extractive evidence matching verifies provenance, not scientific validity."}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    report["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    with sidecar.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return report
