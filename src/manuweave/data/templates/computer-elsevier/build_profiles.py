"""Join confirmed journal layout facts to detailed extracted JSON typography."""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BP_PER_TEX_PT = 72 / 72.27


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def build():
    facts = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "computer-catalog.json").read_text(encoding="utf-8"))
    journals = {j["id"]: j for j in catalog["journals"] if j["publisher_group"] == "Elsevier"}
    mapped, historical = {}, {}
    for fact in facts["facts"]:
        journal = journals["ccf-2026-" + fact["key"]]
        profile = copy.deepcopy(json.loads((ROOT / "elsevier" / "profiles" / (fact["base_profile"] + ".json")).read_text(encoding="utf-8")))
        identifier = "computer-elsevier-" + fact["key"] + ("-rse-2026" if fact.get("historical_route") else "")
        profile.update(id=identifier, name=journal["name"] + " extracted submission format", scope=fact["policy_boundary"],
                       aliases=[identifier, journal["name"] + " " + fact["stage"]], compliance="source_extracted_journal_json_rules")
        profile["journal"] = {"catalog_id": journal["id"], "title": journal["name"], "publisher": journal["publisher"],
                              "categories": journal["categories"], "stage": fact["stage"], "policy_strength": fact["strength"],
                              "historical_route": fact.get("historical_route", False)}
        if fact.get("special_issue"):
            profile["journal"]["special_issue"] = fact["special_issue"]
        origin = {"url": fact["url"], "file": "journal editorial webpage", "locator": fact["locator"], "version": facts["retrieved"]}
        profile["sources"].insert(0, {**origin, "title": fact["authority"], "verified": True})
        template = profile["template"]
        template.update(family="computer-elsevier", source_url=fact["url"], coverage_notes=[fact["policy_boundary"],
                        "Only detailed JSON formatting and source provenance are distributed; publisher templates are not runtime dependencies."])
        profile["page"]["columns"] = fact["columns"]
        profile["extracted_format"]["page"]["columns"] = {"value": fact["columns"], "source": origin}
        for requirement in template["requirements"]:
            if requirement["id"] == "page_columns":
                requirement.update(expected=fact["columns"], source=origin, detail=fact["strength"] + "; " + fact["policy_boundary"])
        if fact.get("double_spacing"):
            # Original 12 pt source-template double-spacing factor: 1.655 × 14.5 TeX pt.
            # The physical value preserves that authoring-template implementation.
            baseline = round(14.5 * 1.655 * BP_PER_TEX_PT, 6)
            for role in ("body", "abstract", "abstract_heading", "reference", "heading1", "heading2", "heading3"):
                profile["rules"][role]["line_spacing_pt"] = baseline
                extracted = profile["extracted_format"]["roles"][role]
                extracted["line_spacing_pt"] = {"value": baseline, "unit": "bp", "source": origin,
                                                "condition": "12 TeX pt source-template typography with standard double-spacing factor 1.655"}
                extracted["source_baseline_tex_pt"] = {"value": 14.5 * 1.655, "unit": "TeX pt", "source": origin}
                for requirement in template["requirements"]:
                    if requirement["id"] == role + "_line_spacing_pt":
                        requirement.update(expected=baseline, source=origin)
        if "times" in fact["options"]:
            for role, properties in profile["rules"].items():
                if properties.get("font") == "Computer Modern Roman":
                    properties["font"] = "Times"
                    profile["extracted_format"]["roles"][role]["font"] = {"value": "Times", "source": origin,
                                                                            "condition": "Documented times option; Times-family source font"}
                    for requirement in template["requirements"]:
                        if requirement["id"] == role + "_font":
                            requirement.update(expected="Times", source=origin)
        profile["extracted_format"]["journal_mapping"] = {"source": origin, "policy_strength": fact["strength"],
                                                               "boundary": fact["policy_boundary"]}
        dump(HERE / "profiles" / (identifier + ".json"), profile)
        (historical if fact.get("historical_route") else mapped)[journal["id"]] = identifier
    dump(HERE / "coverage.json", {"catalog": "computer-catalog.json", "publisher_group": "Elsevier",
                                   "journal_count": len(journals), "executable_journal_layout_count": len(mapped),
                                   "historical_route_count": len(historical),
                                   "journals": [{"catalog_id": key, "title": journal["name"], "profile_id": mapped.get(key),
                                                 "historical_profile_id": historical.get(key),
                                                 "status": "SOURCE_VERIFIED_LAYOUT_SUBSET" if key in mapped else "UNMAPPED",
                                                 "reason": "Confirmed journal layout with detailed extracted JSON typography" if key in mapped else
                                                           "A current journal-specific format source has not been established; no publisher-wide substitution is generated"}
                                                for key, journal in journals.items()]})


if __name__ == "__main__":
    build()
