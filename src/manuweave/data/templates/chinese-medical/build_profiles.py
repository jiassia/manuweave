"""Build partial Word profiles from pinned, independently located source facts.

Only factual formatting values and paraphrased policies ship with the package.
Publisher documents remain outside the repository.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build():
    documents = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))["documents"]
    for identity, fact in documents.items():
        requirements = []

        def add(key, category, target, prop, value, source, locator, checking="xml", certainty="verified", detail=""):
            requirements.append({"id": key, "category": category, "target": target, "property": prop,
                                 "expected": value, "unit": "pt" if prop.endswith("_pt") else None,
                                 "source": {"url": source["url"], "file": source["file"], "locator": locator},
                                 "checking": checking, "certainty": certainty, "applies_to": ["docx"], "detail": detail})

        for role, rule in fact["rules"].items():
            for prop, value in rule.items():
                add(f"{role}-{prop}", "typography", role, prop, value, fact["sources"][0], fact["locators"][role])
        for prop, value in fact["page"].items():
            add(f"page-{prop}", "layout", "page", prop, value, fact["sources"][0], fact["locators"]["page"])
        for item in fact["policies"]:
            add(item["id"], item["category"], item["target"], item["property"], item["expected"],
                fact["sources"][item.get("source_index", 0)], item["locator"],
                item.get("checking", "host"), item.get("certainty", "verified"), item.get("detail", ""))
        profile = {"id": identity, "name": fact["name"], "version": "1.0.0", "aliases": fact["aliases"],
                   "scope": fact["scope"], "compliance": "source_backed_template_partial_coverage",
                   "rules": fact["rules"], "page": fact["page"], "latex": {},
                   "checks": [{"role": role, "property": prop, "expected": value}
                              for role, rule in fact["rules"].items() for prop, value in rule.items()],
                   "sources": [{**source, "retrieved_at": "2026-10-30", "source_verified": True,
                                "submission_compliance_verified": False, "original_file_redistributed": False}
                               for source in fact["sources"]],
                   "template": {"family": "chinese-medical", "source_version": fact["source_version"],
                                "license": "rules_only_source_not_redistributed", "source_url": fact["sources"][0]["url"],
                                "assets": [], "engine_support": {"docx": "partial", "latex": "unsupported"},
                                "requirements": requirements, "coverage_notes": fact["coverage_notes"]}}
        (HERE / "profiles" / f"{identity}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()

