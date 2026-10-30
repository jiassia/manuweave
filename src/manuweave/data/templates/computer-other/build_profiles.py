"""Build declarative formatting profiles from publisher-source numeric facts."""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FORMAT_PROPERTIES = {
    "font", "east_asia_font", "size_pt", "bold", "italic", "font_color", "alignment",
    "line_spacing", "line_spacing_rule", "line_spacing_pt", "space_before_pt", "space_after_pt",
    "first_line_pt", "left_indent_pt", "right_indent_pt",
}
PAGE_PROPERTIES = {
    "width_mm", "height_mm", "margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm",
    "columns", "column_gap_mm", "column_widths_mm", "header_distance_mm", "footer_distance_mm", "mirror_margins",
}


def build(families=None):
    facts = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    for document in facts["documents"]:
        family = document["family"]
        if families and family not in families:
            continue
        extracted = copy.deepcopy(facts["layouts"][document["layout"]])
        requirements = []

        def requirement(target, prop, item, category="typography"):
            requirements.append({
                "id": f"{target}-{prop}", "category": category, "target": target, "property": prop,
                "expected": item["value"], "unit": item["unit"], "source": item["source"],
                "certainty": "verified", "checking": "xml", "applies_to": ["docx", "latex"],
                "detail": "Publisher-source default format; source units and evaluated values are retained in extracted_format.",
            })

        rules = {}
        for role, properties in extracted["roles"].items():
            selected = {prop: item["value"] for prop, item in properties.items() if prop in FORMAT_PROPERTIES and "condition" not in item}
            # Body emphasis belongs to existing manuscript runs; plain source defaults
            # remain explicit facts without deleting intentional inline emphasis.
            if role in {"body", "abstract", "keywords", "reference", "table_body", "figure_caption", "table_caption"}:
                for prop in ("bold", "italic"):
                    if selected.get(prop) is False:
                        selected.pop(prop)
            rules[role] = selected
            for prop in selected:
                requirement(role, prop, properties[prop])
        section_pages = document.get("section_pages")
        page = {prop: item["value"] for prop, item in extracted["page"].items()
                if prop in PAGE_PROPERTIES and ("condition" not in item or section_pages)}
        for prop in page:
            requirement("page", prop, extracted["page"][prop], "layout")
        sections = None
        if page.get("columns") == 2:
            boundary = extracted["page"].get("body_starts_at", {"value": "first_heading1"})
            sections = {"front_matter_columns": 1, "body_columns": 2, "body_starts_at": boundary["value"],
                        "body_column_gap_mm": float(page["column_gap_mm"])}
            if section_pages:
                sections.update(front_matter_page=section_pages["front_matter"], body_page=section_pages["body"])
            for prop, value in sections.items():
                source = boundary.get("source") or extracted["page"]["columns"]["source"]
                requirement("sections", prop, {"value": value, "unit": "enum", "source": source}, "layout")
        # Citation mode is detailed metadata; it never rewrites supplied references or
        # introduces a publisher BibTeX style dependency.
        if document.get("citation_mode"):
            source = document.get("citation_source") or document.get("journal_mapping_source") or next(iter(extracted["roles"]["reference"].values()))["source"]
            extracted.setdefault("references", {})["citation_mode"] = {
                "value": document["citation_mode"], "unit": "enum", "source": source,
            }
        sources = {}
        for item in requirements:
            source = item["source"]
            sources[(source["url"], source.get("sha256"))] = {**source, "source_verified": True,
                                                          "original_file_redistributed": False}
        mapping = document.get("journal_mapping_source")
        if mapping:
            sources[(mapping["url"], mapping.get("sha256"))] = {**mapping, "source_verified": True,
                                                            "original_file_redistributed": False}
        profile = {
            "id": document["id"], "name": document["name"], "version": "2.0.0",
            "catalog_ids": document["catalog_ids"], "aliases": [],
            "scope": "Detailed formatting values extracted from the identified publisher template; applies through the generic document formatting engine.",
            "compliance": "source_extracted_format", "rules": rules, "page": page, "latex": {},
            "sources": list(sources.values()), "extracted_format": extracted,
            "template": {
                "family": family, "source_version": document["layout"],
                "license": "structured_format_facts_only", "source_url": list(sources.values())[0]["url"],
                "assets": [], "engine_support": {"docx": "partial", "latex": "partial"},
                "requirements": requirements,
            },
        }
        if sections:
            profile["sections"] = sections
        folder = ROOT / family / "profiles"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (profile["id"] + ".json")).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
