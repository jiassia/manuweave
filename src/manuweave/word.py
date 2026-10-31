"""Conservative OOXML style learning, edits, and package-integrity auditing."""
from __future__ import annotations

import hashlib
import copy
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from lxml import etree as ET

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "m": "http://schemas.openxmlformats.org/officeDocument/2006/math", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
W = "{" + NS["w"] + "}"
MAX_PACKAGE = 128 * 1024 * 1024
MAX_PART = 32 * 1024 * 1024
PROPERTIES = {"font", "east_asia_font", "size_pt", "bold", "italic", "font_color", "alignment", "line_spacing", "line_spacing_rule", "line_spacing_pt", "space_before_pt", "space_after_pt", "first_line_pt", "left_indent_pt", "right_indent_pt"}
PAGE_PROPERTIES = {"margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "columns", "width_mm", "height_mm", "column_gap_mm", "header_distance_mm", "footer_distance_mm", "mirror_margins", "grid_type", "grid_line_pitch_pt", "column_widths_mm"}
BORDER_EDGES = {"top", "bottom", "left", "right", "insideH", "insideV"}
BORDER_STYLES = {"single", "double", "dashed", "dotted", "nil", "none"}
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _xml(data):
    if re.search(br"<!\s*(DOCTYPE|ENTITY)", data, re.I):
        raise ValueError("DTD and XML entities are forbidden")
    return ET.fromstring(data, parser=ET.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))


def _package(path):
    path = Path(path)
    if path.stat().st_size > MAX_PACKAGE:
        raise ValueError("DOCX package exceeds size limit")
    parts = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name = info.filename
            p = PurePosixPath(name)
            if p.is_absolute() or ".." in p.parts or "\\" in name or ":" in name or name in parts:
                raise ValueError("Unsafe or duplicate ZIP member")
            total += info.file_size
            if info.file_size > MAX_PART or total > MAX_PACKAGE or info.file_size / max(info.compress_size, 1) > 1000:
                raise ValueError("ZIP expansion exceeds safety limits")
            if "vbaproject" in name.lower() or "activex" in name.lower() or name.lower().endswith(".bin"):
                raise ValueError("Active content is forbidden")
            parts[name] = archive.read(info)
            if name.endswith((".xml", ".rels")):
                _xml(parts[name])
    if "word/document.xml" not in parts:
        raise ValueError("Not a Word document")
    main = _xml(parts["word/document.xml"])
    if ET.QName(main).namespace == "http://purl.oclc.org/ooxml/wordprocessingml/main":
        raise ValueError("Strict OOXML Word documents are not supported. Explicitly convert a separate copy to Transitional DOCX with Microsoft Word before inspection; the original must remain unchanged.")
    if main.tag != W + "document" or len(main.findall("w:body", NS)) != 1:
        raise ValueError("Invalid Transitional Word document: expected a w:document root containing exactly one direct w:body.")
    # External relationships are retained as inert data, never resolved.
    return parts


def _val(el, name="val", default=None):
    return default if el is None else el.get(W + name, default)


def _child(parent, local):
    return None if parent is None else parent.find(W + local)


def _ensure(parent, local):
    el = _child(parent, local)
    if el is None:
        el = ET.SubElement(parent, W + local)
    return el


def _props(ppr=None, rpr=None):
    result = {}
    if rpr is not None:
        fonts = _child(rpr, "rFonts")
        for key, attr in (("font", "ascii"), ("east_asia_font", "eastAsia")):
            if fonts is not None and fonts.get(W + attr):
                result[key] = fonts.get(W + attr)
        size = _val(_child(rpr, "sz"))
        if size is not None:
            result["size_pt"] = float(size) / 2
        color = _child(rpr, "color")
        if color is not None and _val(color) is not None and color.get(W + "themeColor") is None:
            result["font_color"] = _val(color).upper() if _val(color) != "auto" else "auto"
        for key, tag in (("bold", "b"), ("italic", "i")):
            child = _child(rpr, tag)
            if child is not None:
                result[key] = _val(child, default="1") not in ("0", "false", "off")
    if ppr is not None:
        alignment = _val(_child(ppr, "jc"))
        if alignment:
            result["alignment"] = alignment
        spacing = _child(ppr, "spacing")
        if spacing is not None:
            for key, attr in (("space_before_pt", "before"), ("space_after_pt", "after")):
                value = spacing.get(W + attr)
                if value is not None:
                    result[key] = float(value) / 20
            line, rule = spacing.get(W + "line"), spacing.get(W + "lineRule")
            if line is not None or rule is not None:
                if rule is not None:
                    result["line_spacing_rule"] = rule
                if line is not None:
                    result["_line_twips"] = float(line)
        indent = _child(ppr, "ind")
        if indent is not None:
            if indent.get(W + "hanging") is not None:
                result["first_line_pt"] = -float(indent.get(W + "hanging")) / 20
            elif indent.get(W + "firstLine") is not None:
                result["first_line_pt"] = float(indent.get(W + "firstLine")) / 20
            for key, attr in (("left_indent_pt", "left"), ("right_indent_pt", "right")):
                if indent.get(W + attr) is not None:
                    result[key] = float(indent.get(W + attr)) / 20
    return result


def _merge_format(base, override):
    """Merge an OOXML format layer without retaining incompatible line units."""
    override = dict(override)
    raw_line = override.pop("_line_twips", None)
    if raw_line is not None:
        effective_rule = override.get("line_spacing_rule", base.get("line_spacing_rule", "auto"))
        override["line_spacing_rule"] = effective_rule
        override["line_spacing" if effective_rule == "auto" else "line_spacing_pt"] = raw_line / (240 if effective_rule == "auto" else 20)
    rule = override.get("line_spacing_rule")
    if rule == "auto" or "line_spacing" in override:
        if "line_spacing" not in override and "line_spacing_pt" in base:
            base["line_spacing"] = base["line_spacing_pt"] / 12
        base.pop("line_spacing_pt", None)
    elif rule in {"exact", "atLeast"} or "line_spacing_pt" in override:
        if "line_spacing_pt" not in override and "line_spacing" in base:
            base["line_spacing_pt"] = base["line_spacing"] * 12
        base.pop("line_spacing", None)
    base.update(override)
    return base


def _property_samples(blocks, key):
    modes = Counter(b["format"]["line_spacing_rule"] for b in blocks if "line_spacing_rule" in b["format"] and ("line_spacing" in b["format"] or "line_spacing_pt" in b["format"]))
    mode = modes.most_common(1)[0][0] if modes else None
    if key == "line_spacing_rule" and mode is None:
        return Counter()
    if key == "line_spacing" and mode != "auto":
        return Counter()
    if key == "line_spacing_pt" and mode not in {"exact", "atLeast"}:
        return Counter()
    return Counter(b["format"][key] for b in blocks if key in b["format"] and (key not in {"line_spacing", "line_spacing_pt"} or b["format"].get("line_spacing_rule") == mode))


class _Styles:
    def __init__(self, parts):
        self.styles = {}
        self.defaults = {}
        self.default_style = None
        self.theme_fonts = {}
        theme_name = next((name for name in parts if name.startswith("word/theme/") and name.endswith(".xml")), None)
        if theme_name:
            theme = _xml(parts[theme_name])
            ans = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            for family in ("major", "minor"):
                font_set = theme.find(f".//a:{family}Font", ans)
                if font_set is None:
                    continue
                for target, tag in (("Ascii", "latin"), ("HAnsi", "latin"), ("EastAsia", "ea"), ("Bidi", "cs")):
                    el = font_set.find("a:" + tag, ans)
                    face = None if el is None else el.get("typeface")
                    if face:
                        self.theme_fonts[family + target] = face
        if "word/styles.xml" in parts:
            root = _xml(parts["word/styles.xml"])
            self.defaults = _merge_format({}, self.properties(root.find("w:docDefaults/w:pPrDefault/w:pPr", NS), root.find("w:docDefaults/w:rPrDefault/w:rPr", NS)))
            for el in root.findall("w:style", NS):
                self.styles[el.get(W + "styleId")] = el
                if el.get(W + "type") == "paragraph" and el.get(W + "default") == "1":
                    self.default_style = el.get(W + "styleId")

    def properties(self, ppr=None, rpr=None):
        result = _props(ppr, rpr)
        fonts = _child(rpr, "rFonts")
        if fonts is not None:
            for key, attrs in (("font", ("ascii", "hAnsi")), ("east_asia_font", ("eastAsia",))):
                if key in result:
                    continue
                for attr in attrs:
                    value = self.theme_fonts.get(fonts.get(W + attr + "Theme"))
                    if value:
                        result[key] = value
                        break
        return result

    def resolve(self, sid, seen=None):
        seen = set() if seen is None else set(seen)
        if sid in seen or sid not in self.styles:
            return {}
        seen.add(sid)
        el = self.styles[sid]
        parent_id = _val(_child(el, "basedOn"))
        result = self.resolve(parent_id, seen)
        if not parent_id and el.get(W + "type") == "paragraph":
            result = dict(self.defaults)
        _merge_format(result, self.properties(_child(el, "pPr"), _child(el, "rPr")))
        return result

    def effective(self, p):
        ppr = _child(p, "pPr")
        result = dict(self.defaults)
        _merge_format(result, self.resolve(_val(_child(ppr, "pStyle"), default=self.default_style)))
        _merge_format(result, self.properties(ppr))
        samples = defaultdict(Counter)
        for run in p.findall(".//w:r", NS):
            text = "".join(run.xpath(".//w:t/text()", namespaces=NS))
            if not text.strip():
                continue
            rp = _child(run, "rPr")
            effective = dict(result)
            _merge_format(effective, self.resolve(_val(_child(rp, "rStyle"))))
            _merge_format(effective, self.properties(None, rp))
            for key, value in effective.items():
                samples[key][value] += max(1, len("".join(run.xpath(".//w:t/text()", namespaces=NS))))
        for key, values in samples.items():
            result[key] = values.most_common(1)[0][0]
        if not samples:
            _merge_format(result, self.properties(None, _child(ppr, "rPr")))
        return result


def _pure_image_paragraph(paragraph, text=None):
    text = "".join(paragraph.xpath(".//w:t/text()", namespaces=NS)) if text is None else text
    return not text.strip() and bool(paragraph.xpath(".//w:drawing | .//w:pict", namespaces=NS)) and not paragraph.xpath(".//m:oMath | .//m:oMathPara", namespaces=NS)


def _role(p, text, index, current):
    instructions = p.xpath(".//w:fldSimple/@w:instr | .//w:instrText/text()", namespaces=NS)
    if any(re.match(r"^\s*TOC(?:\s|$)", instruction, re.I) for instruction in instructions):
        return "toc"
    if _pure_image_paragraph(p, text):
        return "image"
    ppr = _child(p, "pPr")
    sid = _val(_child(ppr, "pStyle"), default="")
    if re.search(r"(?:heading|标题)\s*([1-9])", sid, re.I):
        return "heading" + re.search(r"([1-9])", sid).group(1)
    if sid.lower() in ("title", "标题"):
        return "title"
    if re.match(r"^(摘要|abstract)\s*[:：]?\s*$", text, re.I):
        return "abstract_heading"
    if re.match(r"^(摘要|abstract)\s*[:：]", text, re.I):
        return "abstract"
    if re.match(r"^(关键词|关键字|key\s*words)\s*[:：]", text, re.I):
        return "keywords"
    if re.match(r"^(参考文献|references|bibliography)\s*$", text, re.I):
        return "references_heading"
    caption_match = re.match(r"^(图|figure|fig\.?|表|table)\s*(?:\d+|[IVXLCDM]+(?=\s|[.：:]|$)|[一二三四五六七八九十百]+)", text, re.I)
    if caption_match:
        return "table_caption" if caption_match.group(1).lower() in {"table", "表"} else "figure_caption"
    if sid.lower() == "caption":
        return "caption"
    if re.match(r"^\[\d+\]", text) or (current == "reference" and text.strip()):
        return "reference"
    if re.match(r"^\d+(?:\.\d+)*\s+\S", text):
        depth = len(text.split()[0].split("."))
        return "heading" + str(min(depth, 6))
    if re.match(r"^第[一二三四五六七八九十\d]+[章节]", text):
        return "heading1"
    if p.xpath(".//m:oMath|.//m:oMathPara", namespaces=NS) and not text.strip():
        return "equation"
    if index == 0 and text.strip():
        return "title"
    if current == "abstract" and text.strip():
        return "abstract"
    return "body"


def _page(sect):
    result = {}
    size = _child(sect, "pgSz")
    if size is not None:
        for key, attr in (("width_mm", "w"), ("height_mm", "h")):
            value = size.get(W + attr)
            if value:
                result[key] = round(float(value) * 25.4 / 1440, 4)
    margins = _child(sect, "pgMar")
    if margins is not None:
        for edge in ("top", "bottom", "left", "right", "header", "footer"):
            value = margins.get(W + edge)
            if value:
                result[(edge + "_distance_mm") if edge in {"header", "footer"} else ("margin_" + edge + "_mm")] = round(float(value) * 25.4 / 1440, 4)
    columns = _child(sect, "cols")
    if columns is not None:
        result["columns"] = int(_val(columns, "num", "1"))
    if columns is not None and columns.get(W + "space") is not None:
        result["column_gap_mm"] = float(columns.get(W + "space")) * 25.4 / 1440
    if columns is not None and columns.findall("w:col", NS):
        result["column_widths_mm"] = [float(column.get(W + "w")) * 25.4 / 1440 for column in columns.findall("w:col", NS)]
    grid = _child(sect, "docGrid")
    if grid is not None:
        if grid.get(W + "type") is not None:
            result["grid_type"] = grid.get(W + "type")
        if grid.get(W + "linePitch") is not None:
            result["grid_line_pitch_pt"] = float(grid.get(W + "linePitch")) / 20
    return result


def _canonical(el):
    return ET.tostring(el, method="c14n")


def _borders(table):
    result = {}
    borders = table.find("w:tblPr/w:tblBorders", NS)
    if borders is not None:
        for edge in BORDER_EDGES:
            border = _child(borders, edge)
            if border is not None:
                result[edge] = {"style": _val(border, default="single"), "size_pt": float(_val(border, "sz", "4")) / 8, "color": _val(border, "color", "auto")}
    return result


def _header_border(table):
    values = []
    for cell in table.findall("w:tr/w:tc", NS)[:len(table.findall("w:tr[1]/w:tc", NS))]:
        border = cell.find("w:tcPr/w:tcBorders/w:bottom", NS)
        if border is not None:
            values.append((str(_val(border, default="single")), float(_val(border, "sz", "4")) / 8, str(_val(border, "color", "auto"))))
    if values:
        style, size, color = Counter(values).most_common(1)[0][0]
        return {"style": style, "size_pt": size, "color": color}
    return None


def _running_blocks(parts, styles):
    result = {"header": [], "footer": []}
    for kind in result:
        for name, data in parts.items():
            if re.fullmatch(r"word/" + kind + r"\d*\.xml", name):
                root = _xml(data)
                for index, p in enumerate(root.findall(".//w:p", NS)):
                    result[kind].append({"id": f"{name}:p{index}", "text": "".join(p.xpath(".//w:t/text()", namespaces=NS)), "format": styles.effective(p), "source": {"part": name, "xpath": root.getroottree().getpath(p)}})
    return result


def _column_width(root, element):
    """Return the narrowest column of the object's owning section in mm."""
    body = root.find("w:body", NS)
    child = element
    while child.getparent() is not None and child.getparent() is not body:
        child = child.getparent()
    children = list(body)
    section = None
    if child in children:
        for sibling in children[children.index(child):]:
            section = sibling if sibling.tag == W + "sectPr" else sibling.find("w:pPr/w:sectPr", NS)
            if section is not None:
                break
    page = _page(section)
    width = page.get("width_mm", 215.9) - page.get("margin_left_mm", 25.4) - page.get("margin_right_mm", 25.4)
    columns = _child(section, "cols")
    count = page.get("columns", 1)
    gap = float(_val(columns, "space", "720")) * 25.4 / 1440
    explicit = [] if columns is None else [float(col.get(W + "w")) * 25.4 / 1440 for col in columns.findall("w:col", NS) if col.get(W + "w")]
    return max(1, min(explicit) if explicit and _val(columns, "equalWidth", "1") == "0" else (width - max(0, count - 1) * gap) / max(count, 1))


def _layout_objects(root):
    objects = []
    for index, drawing in enumerate(root.findall(".//w:drawing", NS)):
        extent = drawing.find(".//{" + WP + "}extent")
        if extent is not None:
            objects.append({"id": f"image{index}", "role": "image", "element": drawing, "width_mm": int(extent.get("cx", "0")) / 36000, "height_mm": int(extent.get("cy", "0")) / 36000, "available_width_mm": _column_width(root, drawing), "inline": drawing.find("{" + WP + "}inline") is not None})
    for index, table in enumerate(root.findall(".//w:tbl", NS)):
        widths = [int(el.get(W + "w", "0")) for el in table.findall("w:tblGrid/w:gridCol", NS)]
        preferred = table.find("w:tblPr/w:tblW", NS)
        preferred_width = int(_val(preferred, "w", "0")) if _val(preferred, "type") == "dxa" else 0
        width = max(sum(widths), preferred_width) * 25.4 / 1440
        objects.append({"id": f"table{index}", "role": "table", "element": table, "width_mm": width, "available_width_mm": _column_width(root, table)})
    return objects


def _fit_layout(root):
    changes = []
    for obj in _layout_objects(root):
        width, available = obj["width_mm"], obj["available_width_mm"]
        if width <= available + 0.06:
            continue
        factor = available / width
        element = obj["element"]
        if obj["role"] == "image":
            if not obj["inline"]:
                continue
            extent = element.find(".//{" + WP + "}extent")
            extents = [extent] + element.findall(".//{" + PIC + "}spPr/{" + A + "}xfrm/{" + A + "}ext")
            for extent in extents:
                for attr in ("cx", "cy"):
                    if extent.get(attr):
                        extent.set(attr, str(max(1, round(int(extent.get(attr)) * factor))))
        else:
            for col in element.findall("w:tblGrid/w:gridCol", NS):
                col.set(W + "w", str(max(1, round(int(col.get(W + "w", "0")) * factor))))
            for target in element.findall("w:tblPr/w:tblW", NS) + element.findall("w:tr/w:tc/w:tcPr/w:tcW", NS):
                if _val(target, "type") == "dxa":
                    target.set(W + "w", str(max(1, round(int(_val(target, "w", "0")) * factor))))
        changes.append({"id": obj["id"], "operation": "fit_to_column", "scale": factor, "available_width_mm": available})
    return changes


def _image_linebox_risk(paragraph, styles, block_id):
    heights = []
    for inline in paragraph.findall(".//{" + WP + "}inline"):
        extent = inline.find("{" + WP + "}extent")
        if extent is not None and int(extent.get("cy", "0")) > 0:
            heights.append(int(extent.get("cy")) / 12700)
    if not heights:
        return None
    effective = styles.effective(paragraph)
    if effective.get("line_spacing_rule") != "exact":
        return None
    actual = effective.get("line_spacing_pt")
    # Reserve a small baseline/descent allowance; an exact line equal to the
    # picture height can still trim the picture at the text baseline.
    required = max(heights) + 2
    if actual is not None and actual >= required:
        return None
    return {"id": block_id, "property": "inline_image_linebox", "expected_minimum_pt": required,
            "actual_exact_pt": actual, "pure_image": _pure_image_paragraph(paragraph),
            "reason": "Exact paragraph line height cannot accommodate the inline image; mixed text/image paragraphs require review."}


def _image_linebox_risks(root, styles):
    return [risk for index, paragraph in enumerate(root.findall(".//w:body//w:p", NS))
            if (risk := _image_linebox_risk(paragraph, styles, f"p{index}")) is not None]


def _fit_image_lineboxes(root, styles):
    changes = []
    for index, paragraph in enumerate(root.findall(".//w:body//w:p", NS)):
        risk = _image_linebox_risk(paragraph, styles, f"p{index}")
        if risk is not None and risk["pure_image"]:
            properties = {"line_spacing_rule": "atLeast", "line_spacing_pt": round(risk["expected_minimum_pt"], 2)}
            _set_format(paragraph, properties)
            changes.append({"id": f"p{index}", "operation": "fit_inline_image_linebox", "properties": properties,
                            "reason": "Pure image paragraph must not inherit a text-only exact line height."})
    return changes


def _inventory(parts):
    result = {}
    for name, data in parts.items():
        if name != "word/document.xml" and not re.fullmatch(r"word/(header|footer)\d*\.xml", name):
            result[name] = _hash(data)
            continue
        root = _xml(data)
        # A simple TOC's plain run cache is generated display text. Its field
        # instruction, non-cache objects, and text outside the field stay audited.
        # Complex fields are deliberately not normalized because determining their
        # result boundary requires a separate field-state parser.
        for field in root.findall(".//w:fldSimple", NS):
            if not re.match(r"^\s*TOC(?:\s|$)", _val(field, "instr", ""), re.I):
                continue
            field.attrib.pop(W + "dirty", None)
            for run in list(field):
                if run.tag == W + "r" and all(child.tag in {W + key for key in ("t", "tab", "br", "rPr")} for child in run):
                    # rPr contains formatting only. Reject run caches carrying
                    # nested instruction/object payloads even inside rPr.
                    if not run.xpath(".//m:oMath | .//w:drawing | .//w:object | .//w:fldSimple | .//w:instrText", namespaces=NS):
                        field.remove(run)
        for extent in root.findall(".//{" + WP + "}extent") + root.findall(".//{" + PIC + "}spPr/{" + A + "}xfrm/{" + A + "}ext"):
            extent.attrib.pop("cx", None)
            extent.attrib.pop("cy", None)
        for width in root.findall(".//w:tblGrid/w:gridCol", NS) + root.findall(".//w:tblPr/w:tblW", NS) + root.findall(".//w:tcPr/w:tcW", NS):
            width.attrib.pop(W + "w", None)
        # Compare all semantic XML, ignoring only the precise format nodes we edit.
        for el in list(root.xpath("//w:pPr|//w:rPr|//w:sectPr|//w:tblPr|//w:tcPr", namespaces=NS)):
            if el.tag == W + "sectPr":
                for child in list(el):
                    if child.tag in (W + "pgMar", W + "cols", W + "pgSz"):
                        el.remove(child)
            elif el.tag == W + "pPr":
                for child in list(el):
                    if child.tag in {W + key for key in ("jc", "spacing", "ind", "keepNext", "keepLines")}:
                        el.remove(child)
            elif el.tag == W + "rPr":
                for child in list(el):
                    if child.tag in {W + key for key in ("rFonts", "sz", "szCs", "b", "i", "color")}:
                        el.remove(child)
            elif el.tag == W + "tblPr":
                borders = _child(el, "tblBorders")
                if borders is not None:
                    el.remove(borders)
            elif el.tag == W + "tcPr":
                borders = _child(el, "tcBorders")
                if borders is not None:
                    el.remove(borders)
        # Empty format containers are ignored; semantic sectPr children remain.
        for el in reversed(list(root.xpath("//w:sectPr|//w:pPr|//w:rPr|//w:tblPr|//w:tcPr", namespaces=NS))):
            if not len(el) and not el.attrib:
                el.getparent().remove(el)
        result[name] = _hash(_canonical(root))
    return result


def inspect_docx(path):
    parts = _package(path)
    root = _xml(parts["word/document.xml"])
    styles = _Styles(parts)
    blocks = []
    object_blocks = []
    current = None
    for index, p in enumerate(root.findall(".//w:body//w:p", NS)):
        text = "".join(p.xpath(".//w:t/text()", namespaces=NS))
        role = "image" if _pure_image_paragraph(p, text) else "table_body" if any(a.tag == W + "tc" for a in p.iterancestors()) else _role(p, text, index, current)
        if role == "abstract_heading":
            current = "abstract"
        elif role == "references_heading":
            current = "reference"
        elif role.startswith("heading") or role == "keywords":
            current = None
        blocks.append({"id": f"p{index}", "role": role, "text": text, "source": {"part": "word/document.xml", "xpath": root.getroottree().getpath(p)}, "format": styles.effective(p)})
    for role, tag in (("table", "tbl"), ("image", "drawing"), ("legacy_image", "pict")):
        for index, el in enumerate(root.findall(".//w:" + tag, NS)):
            block = {"id": f"{role}{index}", "role": role, "text": "".join(el.xpath(".//w:t/text()", namespaces=NS)), "source": {"part": "word/document.xml", "xpath": root.getroottree().getpath(el)}}
            if role == "table":
                block["borders"] = _borders(el)
                block["header_bottom"] = _header_border(el)
            object_blocks.append(block)
    result = {"kind": "docx", "path": str(Path(path).resolve()), "sha256": _hash(Path(path).read_bytes()), "blocks": blocks, "object_blocks": object_blocks, "running": _running_blocks(parts, styles), "page": [_page(s) for s in root.findall(".//w:sectPr", NS)], "inventory": _inventory(parts), "objects": {"equations": len(root.xpath("//m:oMath", namespaces=NS)), "tables": len(root.findall(".//w:tbl", NS)), "images": len([k for k in parts if k.startswith("word/media/")]), "fields": len(root.findall(".//w:instrText", NS)) + len(root.findall(".//w:fldSimple", NS)), "bookmarks": len(root.findall(".//w:bookmarkStart", NS))}, "warnings": ["Semantic roles are inferred; review ambiguous short paragraphs.", "Theme fonts and conditional table styles may require host review.", "Applying table border rules normalizes direct cell border overrides; conditional table styles need renderer review."]}
    result["layout_objects"] = [{k: v for k, v in obj.items() if k != "element"} for obj in _layout_objects(root)]
    result["layout_risks"] = [obj for obj in result["layout_objects"] if obj["width_mm"] > obj["available_width_mm"] + 0.06]
    result["linebox_risks"] = _image_linebox_risks(root, styles)
    return result


def learn_docx(path):
    document = inspect_docx(path)
    groups = defaultdict(list)
    for block in document["blocks"]:
        if block["text"].strip() or block["role"] == "equation":
            groups[block["role"]].append(block)
    rules, evidence = {}, []
    for role, blocks in groups.items():
        rules[role] = {}
        for key in sorted(PROPERTIES):
            values = _property_samples(blocks, key)
            if not values:
                continue
            value, count = values.most_common(1)[0]
            rules[role][key] = value
            evidence.append({"role": role, "property": key, "value": value, "unit": "pt" if key.endswith("_pt") else "ratio" if key == "line_spacing" else None, "confidence": count / len(blocks), "sources": [b["source"] for b in blocks if b["format"].get(key) == value], "exceptions": [{"id": b["id"], "value": b["format"].get(key)} for b in blocks if b["format"].get(key) != value]})
    pages = document["page"]
    tables = {}
    table_blocks = [b for b in document["object_blocks"] if b["role"] == "table"]
    for edge in BORDER_EDGES:
        samples = [(b, b["borders"][edge]) for b in table_blocks if edge in b["borders"]]
        if samples:
            values = Counter((v["style"], v["size_pt"], v["color"]) for _, v in samples)
            value, count = values.most_common(1)[0]
            selected = {"style": value[0], "size_pt": value[1], "color": value[2]}
            tables.setdefault("borders", {})[edge] = selected
            evidence.append({"role": "table", "property": "borders." + edge, "value": selected, "unit": "pt", "confidence": count / len(table_blocks), "sources": [b["source"] for b, v in samples if v == selected], "exceptions": [{"id": b["id"], "value": b["borders"].get(edge)} for b in table_blocks if b["borders"].get(edge) != selected]})
    headers = [b for b in table_blocks if b["header_bottom"] is not None]
    if headers:
        values = Counter((b["header_bottom"]["style"], b["header_bottom"]["size_pt"], b["header_bottom"]["color"]) for b in headers)
        value, count = values.most_common(1)[0]
        tables["header_bottom"] = {"style": value[0], "size_pt": value[1], "color": value[2]}
        evidence.append({"role": "table", "property": "header_bottom", "value": tables["header_bottom"], "unit": "pt", "confidence": count / len(table_blocks), "sources": [b["source"] for b in headers], "exceptions": []})
    running = {}
    for kind, blocks in document["running"].items():
        samples = [b for b in blocks if b["text"].strip()]
        if not samples:
            continue
        running[kind] = {}
        for key in PROPERTIES:
            values = _property_samples(samples, key)
            if values:
                value, count = values.most_common(1)[0]
                running[kind][key] = value
                evidence.append({"role": kind, "property": key, "value": value, "unit": "pt" if key.endswith("_pt") else None, "confidence": count / len(samples), "sources": [b["source"] for b in samples if b["format"].get(key) == value], "exceptions": [{"id": b["id"], "value": b["format"].get(key)} for b in samples if b["format"].get(key) != value]})
    return {"id": "learned-" + document["sha256"][:12], "name": "Learned from " + Path(path).name, "version": "1.0.0", "rules": rules, "page": pages[-1] if pages else {}, "tables": tables, "running": running, "evidence": evidence, "source": {"type": "reference_docx", "sha256": document["sha256"]}, "warnings": document["warnings"] + (["Multiple sections: the final section provides the default; section exceptions need review."] if len(pages) > 1 else [])}


def _run_emphasis(p, styles):
    """Resolve visible run emphasis, including inherited character styles."""
    ppr = _child(p, "pPr")
    base = dict(styles.defaults)
    _merge_format(base, styles.resolve(_val(_child(ppr, "pStyle"), default=styles.default_style)))
    values = {}
    for run in p.findall(".//w:r", NS):
        text = "".join(run.xpath(".//w:t/text()", namespaces=NS))
        if not text.strip():
            continue
        effective = dict(base)
        rpr = _child(run, "rPr")
        _merge_format(effective, styles.resolve(_val(_child(rpr, "rStyle"))))
        _merge_format(effective, styles.properties(None, rpr))
        values[run] = {key: effective.get(key, False) for key in ("bold", "italic")}
    return values


def _inline_emphasis(p, styles):
    """Retain mixed-run emphasis relative to the inherited paragraph baseline.

    Uniform run formatting can represent paragraph formatting and is replaced by
    the role rule. Mixed formatting uses the paragraph style, not text length,
    to distinguish local emphasis; a long emphasized span remains an exception.
    """
    if styles is None:
        return {}
    values = _run_emphasis(p, styles)
    ppr = _child(p, "pPr")
    baseline = dict(styles.defaults)
    _merge_format(baseline, styles.resolve(_val(_child(ppr, "pStyle"), default=styles.default_style)))
    mixed = {key for key in ("bold", "italic") if len({props[key] for props in values.values()}) > 1}
    return {run: {key: value for key, value in props.items() if key in mixed and value != baseline.get(key, False)}
            for run, props in values.items()}


def _audit_inline_emphasis(before, after):
    """Check source-local emphasis independently of the new paragraph baseline."""
    issues = []
    before_styles, after_styles = _Styles(before), _Styles(after)
    for name, data in before.items():
        if name != "word/document.xml" and not re.fullmatch(r"word/(header|footer)\d*\.xml", name):
            continue
        if name not in after:
            continue  # Missing parts are covered by the semantic inventory.
        original, result = _xml(data), _xml(after[name])
        for index, (source_p, result_p) in enumerate(zip(original.findall(".//w:p", NS), result.findall(".//w:p", NS))):
            exceptions = _inline_emphasis(source_p, before_styles)
            actual = _run_emphasis(result_p, after_styles)
            for run_index, (source_run, result_run) in enumerate(zip(source_p.findall(".//w:r", NS), result_p.findall(".//w:r", NS))):
                for key, expected in exceptions.get(source_run, {}).items():
                    observed = actual.get(result_run, {}).get(key)
                    if observed != expected:
                        issues.append({"id": f"p{index}" if name == "word/document.xml" else f"{name}:p{index}",
                                       "run_index": run_index, "property": "inline_" + key,
                                       "expected": expected, "actual": observed})
    return issues


def _set_format(p, properties, styles=None):
    emphasis = _inline_emphasis(p, styles)
    ppr = _child(p, "pPr")
    if ppr is None:
        ppr = ET.Element(W + "pPr")
        p.insert(0, ppr)
    if "alignment" in properties:
        _ensure(ppr, "jc").set(W + "val", "both" if properties["alignment"] == "justify" else str(properties["alignment"]))
    for key, attr, factor in (("space_before_pt", "before", 20), ("space_after_pt", "after", 20), ("line_spacing", "line", 240), ("line_spacing_pt", "line", 20)):
        if key in properties:
            spacing = _ensure(ppr, "spacing")
            spacing.set(W + attr, str(round(properties[key] * factor)))
            if key == "line_spacing":
                spacing.set(W + "lineRule", "auto")
            elif key == "line_spacing_pt":
                spacing.set(W + "lineRule", properties["line_spacing_rule"])
    if "line_spacing_rule" in properties:
        _ensure(ppr, "spacing").set(W + "lineRule", properties["line_spacing_rule"])
    if "first_line_pt" in properties:
        indent = _ensure(ppr, "ind")
        hanging = properties["first_line_pt"] < 0
        indent.set(W + ("hanging" if hanging else "firstLine"), str(round(abs(properties["first_line_pt"]) * 20)))
        indent.attrib.pop(W + ("firstLine" if hanging else "hanging"), None)
        indent.attrib.pop(W + "firstLineChars", None)
        indent.attrib.pop(W + "hangingChars", None)
    for key, attr in (("left_indent_pt", "left"), ("right_indent_pt", "right")):
        if key in properties:
            indent = _ensure(ppr, "ind")
            indent.set(W + attr, str(round(properties[key] * 20)))
            indent.attrib.pop(W + attr + "Chars", None)
            indent.attrib.pop(W + ("start" if attr == "left" else "end"), None)
    if any(k in properties for k in ("font", "east_asia_font", "size_pt", "bold", "italic", "font_color")):
        targets = p.findall(".//w:r", NS)
        # Paragraph mark format supports empty paragraphs, including equation paragraphs.
        targets.append(ppr)
        for run in targets:
            rpr = _child(run, "rPr")
            if rpr is None:
                rpr = ET.Element(W + "rPr")
                run.insert(0, rpr) if run.tag == W + "r" else run.append(rpr)
            for key, attrs in (("font", ("ascii", "hAnsi")), ("east_asia_font", ("eastAsia",))):
                if key in properties:
                    fonts = _ensure(rpr, "rFonts")
                    for attr in attrs:
                        fonts.set(W + attr, str(properties[key]))
                        fonts.attrib.pop(W + attr + "Theme", None)
            if "size_pt" in properties:
                for name in ("sz", "szCs"):
                    _ensure(rpr, name).set(W + "val", str(round(properties["size_pt"] * 2)))
            if "font_color" in properties:
                color = _ensure(rpr, "color")
                color.set(W + "val", properties["font_color"].upper() if properties["font_color"] != "auto" else "auto")
                for attr in ("themeColor", "themeTint", "themeShade"):
                    color.attrib.pop(W + attr, None)
            for key, tag in (("bold", "b"), ("italic", "i")):
                if key in properties:
                    value = emphasis.get(run, {}).get(key, properties[key])
                    _ensure(rpr, tag).set(W + "val", "1" if value else "0")
    return [{"run_index": index, "properties": {key: value for key, value in emphasis.get(run, {}).items()
                                                if key in properties and value != properties[key]}}
            for index, run in enumerate(p.findall(".//w:r", NS))
            if any(key in properties and value != properties[key] for key, value in emphasis.get(run, {}).items())]


def _set_border(target, border):
    target.set(W + "val", border.get("style", "single"))
    target.set(W + "sz", str(round(border.get("size_pt", 0.5) * 8)))
    target.set(W + "color", border.get("color", "auto"))


def _heading_role(role):
    return bool(re.fullmatch(r"heading[1-6]", role)) or role in {"abstract_heading", "references_heading"}


def _section_rule(profile):
    raw = profile.get("sections")
    if raw is None:
        return None
    from .models import SectionsRule
    rule = SectionsRule.model_validate(raw).model_dump(exclude_none=True)
    if profile.get("page", {}).get("columns") not in {None, rule["body_columns"]}:
        raise ValueError("page.columns conflicts with the explicit two-region section rule")
    return rule


def _section_semantics(section):
    clone = copy.deepcopy(section)
    for child in list(clone):
        if child.tag in {W + key for key in ("cols", "pgMar", "pgSz", "type", "titlePg", "docGrid")}:
            clone.remove(child)
        elif child.tag == W + "pgNumType":
            child.attrib.pop(W + "start", None)
    return _canonical(clone)


def _section_structure(root, blocks, roles=None, rule=None):
    """Identify only a single-section input or an equivalent managed two-section layout."""
    body = root.find("w:body", NS)
    paragraphs = root.findall(".//w:body//w:p", NS)
    boundary = (rule or {}).get("body_starts_at", "first_heading1")
    boundary_roles = {"marked_body_start": {"body_start"}, "first_abstract": {"abstract", "abstract_zh", "abstract_en"}}.get(boundary, {"heading1"})
    target = next((paragraph for block, paragraph in zip(blocks, paragraphs)
                   if (roles or {}).get(block["id"], block["role"]) in boundary_roles), None)
    if target is None:
        raise ValueError("The two-region layout requires a matching body boundary: " + boundary)
    if target.getparent() is not body:
        raise ValueError("The first heading1 must be a direct body paragraph, outside tables and content controls")
    previous = target.getprevious()
    if previous is None or previous.tag != W + "p":
        raise ValueError("The front matter must end with a paragraph immediately before the first heading1")
    final = body.find("w:sectPr", NS)
    if final is None or final is not body[-1]:
        raise ValueError("A single final body sectPr is required for the two-region layout")
    sections = root.findall(".//w:sectPr", NS)
    front = previous.find("w:pPr/w:sectPr", NS)
    if len(sections) > 2 or any(section is not final and section is not front for section in sections):
        raise ValueError("Existing complex section boundaries conflict with the two-region layout")
    for section in sections:
        first_page = _child(section, "titlePg")
        first_page_active = first_page is not None and _val(first_page, default="1") not in {"0", "false", "off"}
        first_page_controlled = rule is not None and "different_first_page" in rule and (front is None or section is front)
        if (first_page_active and not first_page_controlled) or _child(section, "sectPrChange") is not None:
            raise ValueError("First-page header resets or tracked section changes need a dedicated layout")
        if section.xpath(".//w:numRestart[@w:val='eachSect']", namespaces=NS):
            raise ValueError("Section-based footnote/endnote renumbering conflicts with inserting a section")
    if front is not None:
        if _val(_child(final, "type")) != "continuous" or _section_semantics(front) != _section_semantics(final):
            raise ValueError("Existing sections have different header/footer/note semantics or a non-continuous boundary")
        front_start = _val(_child(front, "pgNumType"), "start")
        body_start = _val(_child(final, "pgNumType"), "start")
        if body_start is not None and body_start != front_start:
            raise ValueError("Existing body page-number restart conflicts with continuous section numbering")
    return previous, front, final


def _section_child(section, name):
    """Insert the controlled section property in OOXML schema order."""
    existing = _child(section, name)
    if existing is not None:
        return existing
    if name == "cols":
        successors = {W + key for key in ("formProt", "vAlign", "noEndnote", "titlePg", "textDirection", "bidi", "rtlGutter", "docGrid", "printerSettings", "sectPrChange")}
        target = ET.Element(W + name)
        index = next((index for index, child in enumerate(section) if child.tag in successors), len(section))
        section.insert(index, target)
        return target
    from docx.oxml import parse_xml
    typed = parse_xml(ET.tostring(section))
    target = getattr(typed, "get_or_add_" + name)()
    if _child(section, name) is None:
        section.insert(list(typed).index(target), ET.Element(W + name))
    return _child(section, name)


def _set_section_columns(section, columns, gap=None):
    cols = _section_child(section, "cols")
    cols.set(W + "num", str(columns))
    cols.set(W + "equalWidth", "1")
    for child in list(cols):
        if child.tag == W + "col":
            cols.remove(child)
    if gap is not None:
        cols.set(W + "space", str(round(gap * 1440 / 25.4)))


def _set_page_properties(section, page):
    for key, value in page.items():
        if key in {"mirror_margins", "column_widths_mm"}:
            continue
        if key == "grid_type":
            _ensure(section, "docGrid").set(W + "type", value)
        elif key == "grid_line_pitch_pt":
            _ensure(section, "docGrid").set(W + "linePitch", str(round(value * 20)))
        elif key == "column_gap_mm":
            _ensure(section, "cols").set(W + "space", str(round(value * 1440 / 25.4)))
        elif key in {"header_distance_mm", "footer_distance_mm"}:
            _ensure(section, "pgMar").set(W + key.split("_")[0], str(round(value * 1440 / 25.4)))
        elif key == "columns":
            _set_section_columns(section, value)
        elif key in {"width_mm", "height_mm"}:
            _ensure(section, "pgSz").set(W + ("w" if key == "width_mm" else "h"), str(round(value * 1440 / 25.4)))
        else:
            edge = key.removeprefix("margin_").removesuffix("_mm")
            _ensure(section, "pgMar").set(W + edge, str(round(value * 1440 / 25.4)))
    if page.get("column_widths_mm"):
        widths = page["column_widths_mm"]
        cols = _ensure(section, "cols")
        cols.set(W + "num", str(len(widths)))
        cols.set(W + "equalWidth", "0")
        for column in cols.findall("w:col", NS):
            cols.remove(column)
        for index, width in enumerate(widths):
            column = ET.SubElement(cols, W + "col")
            column.set(W + "w", str(round(width * 1440 / 25.4)))
            if index < len(widths) - 1:
                column.set(W + "space", cols.get(W + "space", "720"))
    if {"width_mm", "height_mm"} <= set(page):
        _ensure(section, "pgSz").set(W + "orient", "landscape" if page["width_mm"] > page["height_mm"] else "portrait")


def _apply_sections(root, blocks, rule, roles=None):
    previous, front, final = _section_structure(root, blocks, roles, rule)
    inserted = front is None
    if inserted:
        front = copy.deepcopy(final)
        props = _child(previous, "pPr")
        if props is None:
            props = ET.Element(W + "pPr")
            previous.insert(0, props)
        change = _child(props, "pPrChange")
        props.append(front) if change is None else props.insert(list(props).index(change), front)
    _set_section_columns(front, rule["front_matter_columns"])
    _set_section_columns(final, rule["body_columns"], rule.get("body_column_gap_mm"))
    _set_page_properties(front, rule.get("front_matter_page", {}))
    _set_page_properties(final, rule.get("body_page", {}))
    _section_child(final, "type").set(W + "val", "continuous")
    if "different_first_page" in rule:
        if rule["different_first_page"]:
            _section_child(front, "titlePg").set(W + "val", "1")
        else:
            title = _child(front, "titlePg")
            if title is not None:
                front.remove(title)
        title = _child(final, "titlePg")
        if title is not None:
            final.remove(title)
    numbering = _child(final, "pgNumType")
    if numbering is not None:
        numbering.attrib.pop(W + "start", None)
    return {"operation": "insert_continuous_section" if inserted else "update_continuous_sections", "boundary": rule["body_starts_at"], **rule}


def _section_inventory(parts, blocks, rule, roles=None):
    """Normalize only the validated continuous section split, retaining section relationships."""
    root = _xml(parts["word/document.xml"])
    _, front, final = _section_structure(root, blocks, roles, rule)
    if front is not None:
        first_numbering = _child(front, "pgNumType")
        if first_numbering is not None and first_numbering.get(W + "start") is not None:
            _ensure(final, "pgNumType").set(W + "start", first_numbering.get(W + "start"))
        front.getparent().remove(front)
    section_type = _child(final, "type")
    if section_type is not None:
        final.remove(section_type)
    if "different_first_page" in rule:
        title = _child(final, "titlePg")
        if title is not None:
            final.remove(title)
    normalized = dict(parts)
    normalized["word/document.xml"] = ET.tostring(root)
    if "different_odd_even_headers" in rule and "word/settings.xml" in parts:
        settings = _xml(parts["word/settings.xml"])
        for flag in settings.findall("w:evenAndOddHeaders", NS):
            settings.remove(flag)
        normalized["word/settings.xml"] = _canonical(settings)
    return _inventory(normalized)


def _apply_section_settings(parts, rule):
    if "word/settings.xml" in parts:
        settings = _xml(parts["word/settings.xml"])
        if settings.xpath("./w:footnotePr/w:numRestart[@w:val='eachSect'] | ./w:endnotePr/w:numRestart[@w:val='eachSect']", namespaces=NS):
            raise ValueError("Document settings restart notes by section; no section can be inserted safely")
    if "different_odd_even_headers" not in rule:
        return
    if "word/settings.xml" not in parts:
        if rule["different_odd_even_headers"]:
            raise ValueError("Setting different odd/even headers requires an existing native Word settings part")
        return
    from docx.oxml import parse_xml
    settings = parse_xml(parts["word/settings.xml"])
    settings.evenAndOddHeaders_val = rule["different_odd_even_headers"]
    parts["word/settings.xml"] = ET.tostring(settings, xml_declaration=True, encoding="UTF-8", standalone=True)


def _role_properties(profile, role, text=""):
    rules = profile.get("rules", {})
    base = "body" if role == "body_start" else role[:-3] if role.endswith(("_zh", "_en")) else role
    bilingual = {"title", "author", "affiliation", "subtitle", "correspondence", "abstract", "keywords", "figure_caption", "table_caption"}
    if base in bilingual:
        if role != base:
            selected = role
        elif text.strip():
            language = "zh" if re.search(r"[\u3400-\u9fff]", text) else "en" if re.search(r"[A-Za-z]", text) else None
            selected = f"{base}_{language}" if language else base
        else:
            selected = base
        if selected in rules:
            return rules[selected]
    return rules.get(role, rules.get(base, rules.get("caption", {}) if base in {"figure_caption", "table_caption"} else {}))


def apply_docx(source, output, profile, roles=None):
    from .templates import guard_engine
    guard_engine(profile, "docx")
    sections_rule = _section_rule(profile)
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Output must be a new path, distinct from the original")
    if set(profile.get("running", {})) - {"header", "footer"}:
        raise ValueError("Unknown running content rule")
    for properties in list(profile.get("rules", {}).values()) + list(profile.get("running", {}).values()):
        if set(properties) - PROPERTIES:
            raise ValueError("Unknown format property")
        spacing_rule = properties.get("line_spacing_rule")
        if spacing_rule is not None and spacing_rule not in {"auto", "exact", "atLeast"}:
            raise ValueError("Invalid line spacing rule")
        if "line_spacing_pt" in properties and spacing_rule not in {"exact", "atLeast"}:
            raise ValueError("Point line spacing requires exact or atLeast rule")
        if "line_spacing" in properties and (spacing_rule not in {None, "auto"} or "line_spacing_pt" in properties):
            raise ValueError("Automatic ratio conflicts with point line spacing")
        if spacing_rule in {"exact", "atLeast"} and "line_spacing_pt" not in properties:
            raise ValueError("Exact or atLeast line spacing requires points")
        for key, value in properties.items():
            if key in {"font", "east_asia_font"}:
                if not isinstance(value, str) or not value.strip() or len(value) > 200:
                    raise ValueError("Invalid font name")
            elif key in {"bold", "italic"}:
                if not isinstance(value, bool):
                    raise ValueError("Boolean property requires a boolean")
            elif key == "alignment":
                if value not in {"left", "right", "center", "both", "justify", "distribute", "start", "end"}:
                    raise ValueError("Invalid paragraph alignment")
            elif key == "line_spacing_rule":
                continue
            elif key == "font_color":
                if not isinstance(value, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{6}|auto)", value):
                    raise ValueError("Invalid font color")
            elif not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < (-1000 if key in {"first_line_pt", "left_indent_pt", "right_indent_pt"} else 0) or value > 1000:
                raise ValueError("Invalid format measurement")
    if set(profile.get("page", {})) - PAGE_PROPERTIES:
        raise ValueError("Unknown page property")
    for key, value in profile.get("page", {}).items():
        if key == "column_widths_mm":
            from .models import PageRule
            PageRule.model_validate(profile["page"], strict=True)
            continue
        if key == "mirror_margins":
            if not isinstance(value, bool):
                raise ValueError("Mirror margins require a boolean")
            continue
        if key == "grid_type":
            if value not in {"default", "lines", "linesAndChars", "snapToChars"}:
                raise ValueError("Invalid document grid")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("Invalid page measurement")
        if key == "columns":
            if not isinstance(value, int) or not 1 <= value <= 12:
                raise ValueError("Invalid column count")
        elif key in {"width_mm", "height_mm"} and not 20 <= value <= 1500:
            raise ValueError("Invalid page size")
        elif key not in {"width_mm", "height_mm"} and not 0 <= value <= 300:
            raise ValueError("Invalid page margin")
    table_rules = profile.get("tables", {})
    if set(table_rules) - {"borders", "header_bottom"} or set(table_rules.get("borders", {})) - BORDER_EDGES:
        raise ValueError("Unknown table border property")
    borders = list(table_rules.get("borders", {}).values())
    if table_rules.get("header_bottom") is not None:
        borders.append(table_rules["header_bottom"])
    for border in borders:
        if set(border) - {"style", "size_pt", "color"}:
            raise ValueError("Unknown border property")
        if border.get("style", "single") not in BORDER_STYLES:
            raise ValueError("Invalid border style")
        size = border.get("size_pt", 0.5)
        if not isinstance(size, (int, float)) or isinstance(size, bool) or not math.isfinite(size) or not 0 <= size <= 12:
            raise ValueError("Invalid border size")
        if not re.fullmatch(r"(?:[0-9a-fA-F]{6}|auto)", border.get("color", "auto")):
            raise ValueError("Invalid border color")
    parts = _package(source)
    root = _xml(parts["word/document.xml"])
    blocks = inspect_docx(source)["blocks"]
    source_styles = _Styles(parts)
    if sections_rule:
        _section_structure(root, blocks, roles, sections_rule)
        _apply_section_settings(parts, sections_rule)
    paragraphs = root.findall(".//w:body//w:p", NS)
    log = []
    source_hash = _hash(source.read_bytes())
    for p, block in zip(paragraphs, blocks):
        role = (roles or {}).get(block["id"], block["role"])
        if _pure_image_paragraph(p, block["text"]):
            role = "image"
        properties = _role_properties(profile, role, block["text"])
        if _heading_role(role):
            ppr = _child(p, "pPr")
            if ppr is None:
                ppr = ET.Element(W + "pPr")
                p.insert(0, ppr)
            for key in ("keepNext", "keepLines"):
                _ensure(ppr, key).set(W + "val", "1")
            log.append({"id": block["id"], "role": role, "properties": {"keepNext": True, "keepLines": True}, "rollback": {"source_sha256": source_hash, "source": str(source.resolve())}})
        if properties:
            exceptions = _set_format(p, properties, source_styles)
            entry = {"id": block["id"], "role": role, "properties": properties, "rollback": {"source_sha256": source_hash, "source": str(source.resolve())}}
            if exceptions:
                entry["preserved_inline_emphasis"] = exceptions
            log.append(entry)
    for sect in root.findall(".//w:sectPr", NS):
        _set_page_properties(sect, profile.get("page", {}))
    if "mirror_margins" in profile.get("page", {}):
        if "word/settings.xml" not in parts:
            raise ValueError("Mirror margins require a native Word settings part")
        settings = _xml(parts["word/settings.xml"])
        for node in settings.findall("w:mirrorMargins", NS):
            settings.remove(node)
        if profile["page"]["mirror_margins"]:
            ET.SubElement(settings, W + "mirrorMargins")
        parts["word/settings.xml"] = ET.tostring(settings, xml_declaration=True, encoding="UTF-8", standalone=True)
    if sections_rule:
        log.append(_apply_sections(root, blocks, sections_rule, roles))
    if table_rules:
        for index, table in enumerate(root.findall(".//w:tbl", NS)):
            if table_rules.get("borders"):
                # Cell borders override table borders. Clear only those formatting
                # overrides before applying the selected uniform table rules.
                for old in table.findall(".//w:tcPr/w:tcBorders", NS):
                    old.getparent().remove(old)
                table_properties = _child(table, "tblPr")
                if table_properties is None:
                    table_properties = ET.Element(W + "tblPr")
                    table.insert(0, table_properties)
                target = _ensure(table_properties, "tblBorders")
                for edge, border in table_rules["borders"].items():
                    _set_border(_ensure(target, edge), border)
            if table_rules.get("header_bottom") is not None:
                for cell in table.findall("w:tr[1]/w:tc", NS):
                    props = _child(cell, "tcPr")
                    if props is None:
                        props = ET.Element(W + "tcPr")
                        cell.insert(0, props)
                    _set_border(_ensure(_ensure(props, "tcBorders"), "bottom"), table_rules["header_bottom"])
            log.append({"id": f"table{index}", "properties": table_rules, "rollback": {"source_sha256": source_hash, "source": str(source.resolve())}})
    for kind, properties in profile.get("running", {}).items():
        for name, data in list(parts.items()):
            if re.fullmatch(r"word/" + kind + r"\d*\.xml", name):
                running_root = _xml(data)
                for index, paragraph in enumerate(running_root.findall(".//w:p", NS)):
                    exceptions = _set_format(paragraph, properties, source_styles)
                    entry = {"id": f"{name}:p{index}", "properties": properties, "rollback": {"source_sha256": source_hash, "source": str(source.resolve())}}
                    if exceptions:
                        entry["preserved_inline_emphasis"] = exceptions
                    log.append(entry)
                parts[name] = ET.tostring(running_root, xml_declaration=True, encoding="UTF-8", standalone=True)
    log.extend(_fit_layout(root))
    log.extend(_fit_image_lineboxes(root, _Styles(parts)))
    parts["word/document.xml"] = ET.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create protects originals and existing deliverables even during races.
    with output.open("xb") as handle:
        with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                archive.writestr(name, data)
    audit = audit_docx(source, output, profile, roles=roles)
    if audit["content"]["status"] == "FAIL":
        output.unlink()
        raise ValueError("Integrity failure: output rolled back")
    return {"output": str(output.resolve()), "changes": log, "audit": audit}


def audit_docx(before, after, profile=None, roles=None):
    original, result = inspect_docx(before), inspect_docx(after)
    sections_rule = _section_rule(profile) if profile is not None else None
    section_error = None
    if sections_rule:
        try:
            original_inventory = _section_inventory(_package(before), original["blocks"], sections_rule, roles)
            result_inventory = _section_inventory(_package(after), result["blocks"], sections_rule, roles)
            original["inventory"], result["inventory"] = original_inventory, result_inventory
        except ValueError as error:
            section_error = str(error)
    page_rule = dict((profile or {}).get("page", {}))
    for region in (sections_rule or {}).get("front_matter_page", {}), (sections_rule or {}).get("body_page", {}):
        for key in ("grid_type", "grid_line_pitch_pt"):
            if key in region:
                page_rule.setdefault(key, region[key])
    if any(key in page_rule for key in ("mirror_margins", "grid_type", "grid_line_pitch_pt")):
        for document, filename in ((original, before), (result, after)):
            parts = _package(filename)
            if "mirror_margins" in page_rule and "word/settings.xml" in parts:
                settings = _xml(parts["word/settings.xml"])
                for node in settings.findall("w:mirrorMargins", NS):
                    settings.remove(node)
                parts["word/settings.xml"] = _canonical(settings)
            if "grid_type" in page_rule or "grid_line_pitch_pt" in page_rule:
                document_root = _xml(parts["word/document.xml"])
                for grid in document_root.findall(".//w:sectPr/w:docGrid", NS):
                    for property_name, attribute in (("grid_type", "type"), ("grid_line_pitch_pt", "linePitch")):
                        if property_name in page_rule:
                            grid.attrib.pop(W + attribute, None)
                    if not len(grid) and not grid.attrib:
                        grid.getparent().remove(grid)
                parts["word/document.xml"] = ET.tostring(document_root)
            document["inventory"] = _section_inventory(parts, document["blocks"], sections_rule, roles) if sections_rule else _inventory(parts)
    projections = []
    changed = [key for key in set(original["inventory"]) | set(result["inventory"]) if original["inventory"].get(key) != result["inventory"].get(key)]
    issues = [{"id": obj["id"], "property": "column_overflow", "expected": obj["available_width_mm"], "actual": obj["width_mm"]} for obj in result["layout_risks"]]
    issues.extend(result["linebox_risks"])
    issues.extend(_audit_inline_emphasis(_package(before), _package(after)))
    if profile is not None:
        original_roles = {b["id"]: b["role"] for b in original["blocks"]}
        after_root = _xml(_package(after)["word/document.xml"])
        paragraphs = after_root.findall(".//w:body//w:p", NS)
        for block in result["blocks"]:
            role = (roles or {}).get(block["id"], original_roles.get(block["id"], block["role"]))
            if _pure_image_paragraph(paragraphs[int(block["id"][1:])], block["text"]):
                role = "image"
            if _heading_role(role):
                paragraph = paragraphs[int(block["id"][1:])]
                for key in ("keepNext", "keepLines"):
                    value = paragraph.find("w:pPr/w:" + key, NS)
                    if value is None or _val(value, default="1") in {"0", "false", "off"}:
                        issues.append({"id": block["id"], "property": key, "expected": True, "actual": False})
            for key, expected in _role_properties(profile, role, block["text"]).items():
                if key == "alignment" and expected == "justify":
                    expected = "both"
                if key == "font_color" and expected != "auto":
                    expected = expected.upper()
                if key == "size_pt" and expected != round(expected * 2) / 2:
                    source_value = expected
                    expected = round(expected * 2) / 2
                    projections.append({"id": block["id"], "property": key, "source_value": source_value, "word_value": expected, "reason": "OOXML font sizes use half-point units"})
                actual = block["format"].get(key)
                equal = abs(actual - expected) < 0.06 if isinstance(expected, (float, int)) and not isinstance(expected, bool) and isinstance(actual, (float, int)) else actual == expected
                if not equal:
                    issues.append({"id": block["id"], "property": key, "expected": expected, "actual": actual})
        for index, section in enumerate(result["page"]):
            expected_page = dict(profile.get("page", {}))
            if sections_rule:
                region = "front_matter_page" if index == 0 else "body_page"
                expected_page.update(sections_rule.get(region, {}))
                if index == 0 and "column_widths_mm" not in sections_rule.get(region, {}):
                    expected_page.pop("column_widths_mm", None)
            for key, expected in expected_page.items():
                if sections_rule and key == "columns":
                    continue
                if key == "mirror_margins":
                    settings_data = _package(after).get("word/settings.xml")
                    flag = _xml(settings_data).find("w:mirrorMargins", NS) if settings_data else None
                    actual = flag is not None and _val(flag, default="1") not in {"0", "false", "off"}
                else:
                    actual = section.get(key)
                if isinstance(expected, list):
                    equal = isinstance(actual, list) and len(actual) == len(expected) and all(abs(left - right) <= 0.06 for left, right in zip(actual, expected))
                else:
                    equal = actual == expected if isinstance(expected, (bool, str)) else isinstance(actual, (float, int)) and abs(actual - expected) <= 0.06
                if not equal:
                    issues.append({"section": index, "property": key, "expected": expected, "actual": actual})
        if sections_rule:
            if section_error:
                issues.append({"property": "sections", "expected": "a simple continuous front/body split", "actual": section_error})
            else:
                try:
                    _, front, final = _section_structure(after_root, result["blocks"], roles, sections_rule)
                    if front is None:
                        issues.append({"property": "sections", "expected": "a continuous section before first heading1", "actual": "single section"})
                    else:
                        for label, node, expected in (("front_matter", front, 1), ("body", final, 2)):
                            actual = int(_val(_child(node, "cols"), "num", "1"))
                            if actual != expected:
                                issues.append({"section": label, "property": "columns", "expected": expected, "actual": actual})
                        if "body_column_gap_mm" in sections_rule:
                            actual = float(_val(_child(final, "cols"), "space", "720")) * 25.4 / 1440
                            if abs(actual - sections_rule["body_column_gap_mm"]) > 0.03:
                                issues.append({"section": "body", "property": "column_gap_mm", "expected": sections_rule["body_column_gap_mm"], "actual": actual})
                        if _val(_child(final, "pgNumType"), "start") is not None:
                            issues.append({"section": "body", "property": "page_number_restart", "expected": None, "actual": _val(_child(final, "pgNumType"), "start")})
                        if "different_first_page" in sections_rule:
                            actual = _child(front, "titlePg")
                            actual = actual is not None and _val(actual, default="1") not in {"0", "false", "off"}
                            if actual != sections_rule["different_first_page"]:
                                issues.append({"section": "front_matter", "property": "different_first_page", "expected": sections_rule["different_first_page"], "actual": actual})
                    if "different_odd_even_headers" in sections_rule:
                        settings_data = _package(after).get("word/settings.xml")
                        flag = _xml(settings_data).find("w:evenAndOddHeaders", NS) if settings_data else None
                        actual = flag is not None and _val(flag, default="1") not in {"0", "false", "off"}
                        if actual != sections_rule["different_odd_even_headers"]:
                            issues.append({"property": "different_odd_even_headers", "expected": sections_rule["different_odd_even_headers"], "actual": actual})
                except ValueError as error:
                    issues.append({"property": "sections", "expected": "a simple continuous front/body split", "actual": str(error)})
        for block in result["object_blocks"]:
            if block["role"] != "table":
                continue
            for edge, expected in profile.get("tables", {}).get("borders", {}).items():
                actual = block["borders"].get(edge)
                if actual != expected:
                    issues.append({"id": block["id"], "property": "borders." + edge, "expected": expected, "actual": actual})
            expected = profile.get("tables", {}).get("header_bottom")
            if expected is not None and block["header_bottom"] != expected:
                issues.append({"id": block["id"], "property": "header_bottom", "expected": expected, "actual": block["header_bottom"]})
        for kind, properties in profile.get("running", {}).items():
            for block in result["running"][kind]:
                for key, expected in properties.items():
                    actual = block["format"].get(key)
                    if key == "alignment" and expected == "justify":
                        expected = "both"
                    if key == "font_color" and expected != "auto":
                        expected = expected.upper()
                    equal = abs(actual - expected) < 0.06 if isinstance(expected, (float, int)) and not isinstance(expected, bool) and isinstance(actual, (float, int)) else actual == expected
                    if not equal:
                        issues.append({"id": block["id"], "property": key, "expected": expected, "actual": actual})
    return {"content": {"status": "FAIL" if changed else "PASS", "changed_parts": changed}, "style": {"status": "FAIL" if issues else "PASS" if profile is not None else "UNVERIFIED", "issues": issues, "representation_adjustments": projections, "exact_source_sizes": not projections}, "visual": {"status": "UNVERIFIED", "reason": "Requires a real renderer and page inspection"}, "objects_before": original["objects"], "objects_after": result["objects"]}
