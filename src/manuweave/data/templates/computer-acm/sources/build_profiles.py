"""Build ACM paragraph/page profiles using extracted JSON values only.

This builder never reads or installs publisher classes, styles or templates.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAMILY = ROOT / "computer-acm"
TEX_PT_TO_BP = 72 / 72.27
POINT_PROPERTIES = {
    "size_pt", "line_spacing_pt", "space_before_pt", "space_after_pt", "first_line_pt",
    "left_indent_pt", "right_indent_pt",
}
PARAGRAPH_PROPERTIES = POINT_PROPERTIES | {"font", "bold", "italic", "alignment"}
EXECUTABLE_ROLES = {
    "title", "subtitle", "author", "affiliation", "correspondence", "body", "abstract",
    "abstract_heading", "keywords", "heading1", "heading2", "heading3", "heading4",
    "references_heading", "reference", "figure_caption", "table_caption", "table_body", "equation",
}
PAGE_PROPERTIES = {
    "width_mm", "height_mm", "margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm",
    "columns", "column_gap_mm", "header_distance_mm", "footer_distance_mm", "mirror_margins",
}


def executable_rules(extracted):
    """Convert physical points; retain conditional behavior in the extraction ledger."""
    rules = {}
    for role, facts in extracted["roles"].items():
        if role not in EXECUTABLE_ROLES:
            continue
        properties = {}
        for prop, fact in facts.items():
            if prop not in PARAGRAPH_PROPERTIES:
                continue
            if role == "reference" and prop in {"left_indent_pt", "first_line_pt"}:
                if extracted["references"]["default_citation_style"]["value"] != "author_year":
                    continue
            if role in {"figure_caption", "table_caption", "table_body"} and prop == "alignment":
                continue
            value = fact["value"]
            if prop in POINT_PROPERTIES:
                if fact["unit"] != "tex_pt":
                    raise ValueError("Extracted ACM point values must identify TeX points")
                value = round(value * TEX_PT_TO_BP, 8)
            properties[prop] = value
        if "line_spacing_pt" in properties:
            properties["line_spacing_rule"] = "atLeast"
        rules[role] = properties
    return rules


def attach_contract(item):
    """Bind every executed property to its extracted value and explicit projection."""
    extracted = item["extracted_format"]
    requirements = []

    def add(target, prop, expected, fact, category, projection="identity"):
        detail = fact.get("condition", "Extracted publisher-template formatting value.")
        if projection == "tex_pt_to_bp":
            detail += " Executable points are physical bp, converted from the unchanged source TeX points by 72/72.27."
        requirements.append({
            "id": target + "-" + prop, "category": category, "target": target,
            "property": prop, "expected": copy.deepcopy(expected),
            "unit": "bp" if projection == "tex_pt_to_bp" else "line_spacing_rule" if projection == "tex_natural_baseline_to_word_minimum" else fact["unit"],
            "source": copy.deepcopy(fact["source"]), "certainty": "verified",
            "checking": "xml", "applies_to": ["docx", "latex"], "detail": detail,
            "source_projection": {"source_value": copy.deepcopy(fact["value"]),
                                  "source_unit": fact["unit"], "operation": projection},
        })

    for target, properties in [*item["rules"].items(), *item["running"].items()]:
        for prop, expected in properties.items():
            facts = extracted["roles"][target]
            if prop == "line_spacing_rule":
                fact = copy.deepcopy(facts["line_spacing_pt"])
                fact["condition"] = facts["word_line_spacing_representation"]["condition"]
                projection = "tex_natural_baseline_to_word_minimum"
            else:
                fact = facts[prop]
                projection = "tex_pt_to_bp" if prop in POINT_PROPERTIES else "identity"
            category = "font" if prop in {"font", "size_pt", "bold", "italic"} else "paragraph"
            add(target, prop, expected, fact, category, projection)
    for prop, expected in item["page"].items():
        add("page", prop, expected, extracted["page"][prop], "layout")
    section_evidence = {
        "front_matter_columns": ("front_matter_span_roles", "full_width_front_matter"),
        "body_columns": ("columns", "identity"),
        "body_starts_at": ("body_starts_at_role", "role_to_section_boundary"),
        "body_column_gap_mm": ("column_gap_mm", "identity"),
        "different_first_page": ("first_page_header_visible", "separate_first_page_header"),
        "different_odd_even_headers": ("running_header_slots", "separate_odd_even_header_slots"),
    }
    for prop, expected in item.get("sections", {}).items():
        key, projection = section_evidence[prop]
        add("sections", prop, expected, extracted["page"][key], "layout", projection)
    item["template"] = {
        "family": "acmart-extracted-json", "source_version": "2.20",
        "source_url": "https://ctan.org/pkg/acmart",
        "license": "rules_only_source_not_redistributed", "assets": [],
        "engine_support": {"docx": "partial", "latex": "partial"},
        "requirements": requirements,
        "coverage_notes": [
            "Executed paragraph, page, running-content and section properties are individually linked to the extracted JSON facts.",
            "Source TeX-point values retain their original precision; executed point dimensions use physical bp.",
            "TeX natural baselines map to Word minimum line boxes through atLeast; this representation is not a publisher requirement for fixed Word spacing.",
            "Conditional inline typography, run-in headings and caption details remain explicitly recorded in extracted_format.",
        ],
    }


def profile(identifier, name, mode, extracted, aliases=None):
    extracted = copy.deepcopy(extracted)
    for facts in extracted["roles"].values():
        if "line_spacing_pt" in facts:
            facts["word_line_spacing_representation"] = {
                "value": "atLeast", "unit": "engine_mapping",
                "source": copy.deepcopy(facts["line_spacing_pt"]["source"]),
                "condition": "Represent the TeX natural baseline as a Word minimum. Tall inline mathematics or glyphs may increase a line box; this is not a publisher requirement for fixed Word spacing.",
            }
    extracted["page"]["mirror_margins"] = copy.deepcopy(extracted["page"]["two_sided"])
    item = {
        "id": identifier, "name": name, "version": "2.0.0",
        "scope": "Publisher-template typography and layout values extracted into JSON. Paragraph and page values drive the generic engines; inline and column exceptions remain explicit in extracted_format.",
        "aliases": aliases or [], "format_origin": "publisher_template_extraction",
        "rules": executable_rules(extracted),
        "page": {key: fact["value"] for key, fact in extracted["page"].items() if key in PAGE_PROPERTIES},
        "latex": {"documentclass": "article", "options": ["10pt"], "packages": {}},
        "sources": [], "extracted_format": extracted,
    }
    running = {}
    for role in ("header", "footer"):
        facts = extracted["roles"][role]
        running[role] = {
            "font": facts["font"]["value"],
            "size_pt": facts["size_pt"]["value"] * TEX_PT_TO_BP,
            "line_spacing_pt": facts["line_spacing_pt"]["value"] * TEX_PT_TO_BP,
            "line_spacing_rule": "atLeast", "bold": False, "italic": False,
        }
    item["running"] = running
    if extracted["page"]["columns"]["value"] == 2:
        item["sections"] = {
            "front_matter_columns": 1, "body_columns": 2,
            "body_starts_at": "first_abstract",
            "body_column_gap_mm": extracted["page"]["column_gap_mm"]["value"],
            "different_first_page": True, "different_odd_even_headers": True,
        }
    attach_contract(item)
    return item


def source_list(extracted):
    sources = {}

    def visit(value):
        if isinstance(value, dict):
            if "source" in value:
                source = value["source"]
                key = (source["url"], source.get("file"), source.get("sha256"))
                sources.setdefault(key, copy.deepcopy(source))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(extracted)
    return list(sources.values())


def build():
    ledger = json.loads((FAMILY / "sources/extracted-layouts.json").read_text(encoding="utf-8"))
    selection = json.loads((FAMILY / "sources/journals.json").read_text(encoding="utf-8"))
    layouts = ledger["layouts"]
    (FAMILY / "profiles").mkdir(exist_ok=True)
    for journal in selection["journals"]:
        code, mode = journal["code"], journal["format"]
        extracted = copy.deepcopy(layouts[mode])
        extracted["journal_mapping"] = {
            "journal_code": {"value": code, "unit": "code", "source": journal["mapping_source"]},
            "format": {"value": mode, "unit": "name", "source": journal["mapping_source"]},
        }
        if code == "TOG":
            extracted["references"]["default_citation_style"] = {
                "value": "author_year", "unit": "citation_style", "source": journal["citation_source"],
                "condition": "SIGGRAPH and SIGGRAPH Asia Technical Papers journal track.",
            }
        if code == "PACMPL":
            extracted["references"]["allowed_citation_styles"] = {
                "value": ["author_year", "numeric"], "unit": "citation_styles",
                "source": journal["author_format_source"],
            }
        item = profile("acm-" + code.lower() + "-article-publication",
                       journal["title"] + ": extracted publication layout", mode, extracted,
                       [code + " publication", journal["title"] + " publication"])
        item["catalog_ids"] = journal["catalog_ids"]
        item["journal"] = {"title": journal["title"], "publisher": "ACM", "code": code,
                           "manuscript_type": "research_article", "stage": "publication"}
        if journal.get("track"):
            item["journal"]["track"] = journal["track"]
        item["sources"] = source_list(extracted)
        (FAMILY / "profiles" / (item["id"] + ".json")).write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    modes = [
        ("manuscript", "manuscript"), ("manuscript-review-anonymous", "manuscript"),
        ("acmsmall", "acmsmall"), ("acmlarge", "acmlarge"), ("acmtog", "acmtog"),
        ("sigconf", "sigconf"), ("sigconf-review-anonymous", "sigconf"),
        ("sigplan", "sigplan"), ("acmengage", "acmengage"), ("acmcp", "acmcp"),
    ]
    for suffix, mode in modes:
        extracted = copy.deepcopy(layouts[mode])
        if "review" in suffix:
            extracted["page"]["line_numbers"] = {
                "value": True, "unit": "boolean",
                "source": dict(ledger["source_registry"]["acmart"], locator="lines 2922-2965"),
                "condition": "Original review variant; this formatting record does not remove authors or rewrite manuscript content.",
            }
        item = profile("acm-" + suffix, "ACM " + suffix + ": extracted layout", mode, extracted,
                       ["acmart " + suffix, "acm " + suffix + " template"])
        item["sources"] = source_list(extracted)
        path = ROOT / "acm/profiles" / (item["id"] + ".json")
        path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
