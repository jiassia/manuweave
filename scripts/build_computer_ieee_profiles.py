"""Build IEEE journal profiles from checked-in extracted JSON facts, without downloads."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "src/manuweave/data/templates"
FAMILY = ROOT / "computer-ieee"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def make_profile(identifier, title, layout, source_url, aliases=()):
    rules, page = deepcopy(layout["rules"]), deepcopy(layout["page"])
    extracted = deepcopy(layout["extracted_format"])
    requirements = []
    formats = list(rules.items()) + [("page", page)]
    sections = layout.get("sections")
    if sections:
        formats.append(("sections", sections))
    for target, values in formats:
        for prop, value in values.items():
            source = layout["class_source"]
            raw_prop = {"font": "family", "size_pt": "size", "line_spacing_pt": "baseline", "bold": "series", "italic": "shape"}.get(prop, prop)
            facts = extracted.get("page", {}) if target in {"page", "sections"} else extracted["roles"].get(target, {})
            source = facts.get(raw_prop, {}).get("source", source)
            requirements.append({
                "id": f"{target}-{prop.replace('_', '-')}", "category": "layout" if target in {"page", "sections"} else "typography",
                "target": target, "property": prop, "expected": value,
                "unit": "mm" if prop.endswith("_mm") else "bp" if prop.endswith("_pt") else None,
                "source": source, "certainty": "verified", "checking": "xml", "applies_to": ["docx", "latex"],
                "detail": "Executable projection of the extracted source option branch. Physical bp values retain original TeX pt measurements in extracted_format; Word font sizes require half-point representation.",
            })
    profile = {
        "id": identifier, "name": title + " extracted format", "version": "2.0.0",
        "scope": "Formatting extracted from the explicitly selected source template. Journal selector article types do not establish initial/final submission stage or published-page layout.",
        "aliases": list(dict.fromkeys(aliases)), "rules": rules, "page": page,
        "latex": {"documentclass": "article", "options": [], "packages": {}},
        "sources": [{"url": source_url, "title": title + " original format source", "verified": True,
                     "retrieved": "2026-10-30", "verification_scope": "Detailed source font, spacing, page, caption, equation and reference formatting facts; original files are not distributed."}],
        "template": {"family": "IEEE extracted formatting", "source_version": layout["source_mode"],
                     "license": "Formatting facts extracted from original source; no original source redistributed",
                     "source_url": source_url, "assets": [], "engine_support": {"docx": "partial", "latex": "partial"},
                     "requirements": requirements, "coverage_notes": layout["coverage_notes"]},
        "extracted_format": extracted,
    }
    if sections:
        profile["sections"] = deepcopy(sections)
    return profile


def build():
    facts = read(FAMILY / "source-facts.json")
    layouts = read(FAMILY / "extracted-layouts.json")["layouts"]
    by_package = {}
    for key, layout in layouts.items():
        if layout["source_package_id"] is not None:
            by_package.setdefault(int(layout["source_package_id"]), []).append(layout)
    catalog = read(ROOT / "computer-catalog.json")
    journals = {item["id"]: item for item in catalog["journals"]}
    generated = []
    for journal in facts["journal_mappings"]:
        for binding in journal["latex_templates"]:
            package_id = binding["template_meta"]["id"]
            for layout in by_package[package_id]:
                # SPL package has two equivalent LaTeX entry points; the measured
                # bare_jrnl is the original LaTeX article entry point.
                kind = re.sub(r"[^a-z0-9]+", "-", binding["article_type"]["name"].lower()).strip("-")
                alternate = "-one-column" if layout["source_mode"].endswith("one-column") else ""
                identifier = f"computer-ieee-{journal['selector_publication_id']}-{kind}{alternate}"
                name = f"{journal['journal_name']} {binding['article_type']['name']}{' one-column' if alternate else ''}"
                aliases = [name, f"{journal['abbreviation']} {binding['article_type']['name']}{alternate}".strip()]
                profile = make_profile(identifier, name, layout, facts["template_packages"][str(package_id)]["download_source"]["url"], aliases)
                source_journal = journals[journal["catalog_id"]]
                profile["journal"] = {"catalog_id": journal["catalog_id"], "title": journal["journal_name"],
                                      "publisher": source_journal["publisher"], "categories": source_journal.get("categories", []),
                                      "article_type": binding["article_type"]["name"], "stage": "authoring_manuscript_template",
                                      "policy_strength": "official_template_selector_binding", "historical_route": False}
                profile["extracted_format"]["journal_binding"] = {
                    "catalog_id": journal["catalog_id"], "selector_publication_id": journal["selector_publication_id"],
                    "selector_publication_name": journal["selector_publication_name"],
                    "mapping_id": binding["mapping_id"], "template_meta_id": package_id,
                    "article_type": binding["article_type"], "source": {"url": journal["api_source"]["url"],
                    "file": "official IEEE Template Selector API response", "locator": f"mapping id {binding['mapping_id']}, templateMeta id {package_id}",
                    "sha256": journal["api_source"]["sha256"]},
                }
                write(FAMILY / "profiles" / (identifier + ".json"), profile)
                generated.append(identifier)
    for key, layout in layouts.items():
        if not key.startswith("old-"):
            continue
        identifier = key.removeprefix("old-")
        path = ROOT / "ieee/profiles" / (identifier + ".json")
        previous = read(path)
        aliases = previous.get("aliases", [])
        profile = make_profile(identifier, "IEEEtran 1.8b " + identifier.removeprefix("ieee-"), layout,
                               "https://ctan.org/pkg/ieeetran", aliases)
        write(path, profile)
    return generated


if __name__ == "__main__":
    print(f"Built {len(build())} source-bound IEEE journal profiles and 9 generic source modes")
