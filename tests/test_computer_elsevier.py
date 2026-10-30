"""Journal mappings override confirmed properties without inventing coverage."""
import json

import pytest

from manuweave.models import StyleProfile
from manuweave.templates import ROOT, validate_template

FAMILY = ROOT / "computer-elsevier"
PROFILES = sorted((FAMILY / "profiles").glob("*.json"))


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_journal_format_contains_executable_detailed_json_only(path):
    profile = json.loads(path.read_text(encoding="utf-8"))
    StyleProfile.model_validate(profile)
    validate_template(profile)
    assert profile["journal"]["catalog_id"].startswith("ccf-2026-")
    assert profile["template"]["assets"] == []
    assert not profile["template"].get("fixture")
    assert profile["latex"]["documentclass"] == "article"
    assert len(profile["rules"]) >= 12
    assert len(profile["template"]["requirements"]) >= 80
    assert profile["extracted_format"]["page"]["columns"]["value"] == profile["page"]["columns"]


def test_double_spacing_has_measured_physical_point_values():
    for journal in ("pattern-recognition", "signal-processing"):
        profile = json.loads((FAMILY / "profiles" / ("computer-elsevier-" + journal + ".json")).read_text(encoding="utf-8"))
        assert profile["rules"]["body"]["line_spacing_pt"] == pytest.approx(14.5 * 1.655 * 72 / 72.27)
        assert profile["rules"]["body"]["line_spacing_rule"] == "atLeast"
        assert profile["rules"]["body"]["line_spacing_pt"] > profile["rules"]["title"]["line_spacing_pt"]
        assert profile["extracted_format"]["roles"]["body"]["line_spacing_pt"]["source"]["url"].startswith("https://shop.elsevier.com/")


def test_coverage_keeps_historical_and_unmapped_routes_separate():
    coverage = json.loads((FAMILY / "coverage.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "computer-catalog.json").read_text(encoding="utf-8"))
    expected = {j["id"] for j in catalog["journals"] if j["publisher_group"] == "Elsevier"}
    assert {j["catalog_id"] for j in coverage["journals"]} == expected
    assert coverage["journal_count"] == len(expected)
    assert coverage["executable_journal_layout_count"] + coverage["historical_route_count"] == len(PROFILES)
    assert all(j["profile_id"] is None for j in coverage["journals"] if j["status"] == "UNMAPPED")
    fgcs = next(j for j in coverage["journals"] if j["catalog_id"] == "ccf-2026-future-generation-computer-systems")
    assert fgcs["status"] == "UNMAPPED" and fgcs["profile_id"] is None
    assert fgcs["historical_profile_id"].endswith("rse-2026")
