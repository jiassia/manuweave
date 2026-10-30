"""Compile the three audited Word layout mappings without network access."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))


def build_profiles():
    from manuweave.presets import validate_profile

    facts = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    profiles = []
    for entry in facts["entries"]:
        profile = copy.deepcopy(entry["metadata"])
        profile["rules"], profile["page"] = {}, {}
        requirements = []
        for fact in entry["format_facts"]:
            targets = facts["text_paragraph_roles"] if fact["target"] == "text_paragraphs" else [fact["target"]]
            for target in targets:
                requirement = copy.deepcopy(fact)
                requirement["target"] = target
                if fact["target"] == "text_paragraphs":
                    requirement["id"] = target + "-" + fact["property"]
                    requirement["source_fact_id"] = fact["id"]
                requirements.append(requirement)
                properties = profile["page"] if target == "page" else profile["rules"].setdefault(target, {})
                properties[fact["property"]] = fact["expected"]
        profile["template"]["requirements"] = requirements
        profiles.append(validate_profile(profile))
    return profiles


def main():
    output = HERE / "profiles"
    output.mkdir(exist_ok=True)
    for profile in build_profiles():
        path = output / (profile["id"] + ".json")
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(profile["id"])


if __name__ == "__main__":
    main()
