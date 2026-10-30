"""Build only the confirmed, source-backed Chinese manuscript-format profiles."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build():
    data = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    (HERE / "profiles").mkdir(exist_ok=True)
    for identity, fact in data["documents"].items():
        requirements = []

        def add(identifier, category, target, prop, value, source_index, locator, checking="xml", detail="", unit=None):
            source = fact["sources"][source_index]
            requirements.append({
                "id": identifier, "category": category, "target": target, "property": prop,
                "expected": value, "unit": unit,
                "source": {"url": source["url"], "file": source["file"], "locator": locator,
                           "sha256": source["sha256"], "retrieved_at": "2026-10-30"},
                "certainty": "verified", "checking": checking, "applies_to": ["docx"], "detail": detail,
            })

        for role, rule in fact["rules"].items():
            for prop, value in rule.items():
                origin = fact["rule_sources"][role][prop]
                add(f"{role}-{prop}", "typography", role, prop, value, origin["source_index"], origin["locator"],
                    detail=origin.get("detail", ""), unit="pt" if prop.endswith("_pt") else None)
        for prop, value in fact["page"].items():
            origin = fact["page_sources"][prop]
            add(f"page-{prop}", "layout", "page", prop, value, origin["source_index"], origin["locator"])
        for policy in fact["policies"]:
            add(policy["id"], policy["category"], policy["target"], policy["property"], policy["expected"],
                policy.get("source_index", 0), policy["locator"], checking="host", detail=policy.get("detail", ""), unit=policy.get("unit"))
        profile = {
            "id": identity, "name": fact["name"], "version": "1.0.0", "aliases": fact["aliases"],
            "scope": fact["scope"], "compliance": "source_backed_template_partial_coverage",
            "rules": fact["rules"], "page": fact["page"], "latex": {},
            "sources": [{**s, "retrieved_at": "2026-10-30", "source_verified": True,
                         "submission_compliance_verified": False, "original_file_redistributed": False} for s in fact["sources"]],
            "checks": [{"role": role, "property": prop, "expected": value}
                       for role, rule in fact["rules"].items() for prop, value in rule.items()],
            "template": {
                "family": "chinese-multidisciplinary", "source_version": fact["source_version"],
                "license": "rules_only_source_not_redistributed", "source_url": fact["sources"][0]["url"],
                "assets": [], "engine_support": {"docx": "partial", "latex": "unsupported"},
                "requirements": requirements, "coverage_notes": fact["coverage_notes"],
            },
        }
        (HERE / "profiles" / f"{identity}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
