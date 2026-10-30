"""Build Word formatting profiles from measured official manuscript templates.

Only structured typography/layout facts ship here. Original publisher documents
and temporary conversions remain outside the package.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build():
    facts = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    for identity, fact in facts["documents"].items():
        source = fact["source"]
        requirements = []

        def add(target, prop, value):
            requirements.append({
                "id": f"{target}-{prop}",
                "category": "layout" if target in {"page", "sections"} else "typography",
                "target": target, "property": prop, "expected": value,
                "unit": "pt" if prop.endswith("_pt") else "mm" if prop.endswith("_mm") else None,
                "source": {"url": source["url"], "file": source["file"],
                           "locator": fact.get("property_locators", {}).get(f"{target}.{prop}", fact["locators"][target])},
                "certainty": "verified", "checking": "xml", "applies_to": ["docx"],
                "detail": "Observed manuscript run, inherited style or section property in the official template; editorial annotation typography is excluded.",
            })

        for role, properties in fact["rules"].items():
            for prop, value in properties.items():
                add(role, prop, value)
        for target in ("page", "sections"):
            for prop, value in fact.get(target, {}).items():
                add(target, prop, value)
        profile = {
            "id": identity, "name": fact["name"], "version": "1.0.0", "aliases": fact["aliases"],
            "scope": "Official Word manuscript template typography and layout captured from semantic content runs and resolved inheritance; source-specific stage and section limits are recorded.",
            "compliance": "source_backed_template_partial_coverage",
            "manuscript_stage": fact.get("manuscript_stage", "official_manuscript_template"),
            "rules": fact["rules"], "page": fact["page"], "latex": {},
            "sources": [{**source, "source_verified": True, "original_file_redistributed": False,
                         "submission_compliance_verified": False}],
            "template": {
                "family": "computer-chinese", "source_version": fact["source_version"],
                "license": "rules_only_source_not_redistributed", "source_url": source["url"],
                "assets": [], "engine_support": {"docx": "partial", "latex": "unsupported"},
                "requirements": requirements, "coverage_notes": fact["coverage_notes"],
            },
        }
        if fact.get("sections"):
            profile["sections"] = fact["sections"]
        if fact.get("host_role_requirements"):
            profile["host_role_requirements"] = fact["host_role_requirements"]
        if fact.get("extracted_format"):
            profile["extracted_format"] = fact["extracted_format"]
        destination = HERE / "profiles" / f"{identity}.json"
        destination.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
