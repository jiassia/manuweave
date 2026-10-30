"""Publisher formats retain detailed source facts without publisher runtime files."""
import json
import math

import pytest

from manuweave.models import StyleProfile
from manuweave.latex import apply_latex, inspect_latex
from manuweave.templates import ROOT, materialize_fixture, validate_template

PROFILES = sorted((ROOT / "elsevier" / "profiles").glob("*.json")) + sorted((ROOT / "revtex" / "profiles").glob("*.json"))


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_detailed_json_modes_are_self_contained_and_use_physical_points(path):
    profile = json.loads(path.read_text(encoding="utf-8"))
    StyleProfile.model_validate(profile)
    validate_template(profile)
    assert profile["template"]["assets"] == []
    assert not profile["template"].get("fixture")
    assert profile["latex"]["documentclass"] == "article"
    assert not profile["latex"].get("bibliography_style")
    extracted = profile["extracted_format"]
    assert {"body", "title", "author", "affiliation", "abstract", "heading1", "heading2", "heading3", "caption", "reference"} <= extracted["roles"].keys()
    for role in extracted["roles"]:
        if "source_size_tex_pt" not in extracted["roles"][role]:
            continue
        raw = extracted["roles"][role]["source_size_tex_pt"]["value"]
        assert math.isclose(profile["rules"][role]["size_pt"], raw * 72 / 72.27, abs_tol=1e-6)
        assert extracted["roles"][role]["size_pt"]["unit"] == "bp"
    assert profile["page"]["width_mm"] > 150
    assert profile["page"]["height_mm"] > 200
    assert extracted["captions"]["short_alignment"]["value"] == ("justify" if profile["id"] == "revtex-rmp-reprint" else "center")
    assert extracted["equations"]["number_position"]["value"] == "right"
    for requirement in profile["template"]["requirements"]:
        assert requirement["source"]["url"].startswith("https://")
        assert len(requirement["source"]["sha256"]) == 64
        assert "anchor" not in requirement["source"]


def test_distinct_source_modes_and_important_typographic_differences_survive():
    profiles = [json.loads(p.read_text(encoding="utf-8")) for p in PROFILES]
    signatures = {(p["extracted_format"]["source_mode"]["documentclass"], tuple(p["extracted_format"]["source_mode"]["options"])) for p in profiles}
    assert len(signatures) == len(profiles) == 20
    lookup = {p["id"]: p for p in profiles}
    assert lookup["elsevier-preprint-numeric"]["page"]["width_mm"] == pytest.approx(215.9, abs=.001)
    assert lookup["elsevier-preprint-numeric"]["rules"]["title"]["size_pt"] == pytest.approx(17.28 * 72 / 72.27)
    assert lookup["elsevier-preprint-numeric"]["rules"]["heading1"]["size_pt"] == pytest.approx(12 * 72 / 72.27)
    assert lookup["elsevier-cas-sc"]["rules"]["abstract"]["size_pt"] == pytest.approx(8 * 72 / 72.27)
    assert lookup["revtex-aip-jcp-reprint"]["rules"]["reference"]["size_pt"] == pytest.approx(8 * 72 / 72.27)
    assert lookup["revtex-aps-reprint"]["rules"]["reference"]["size_pt"] == pytest.approx(9 * 72 / 72.27)
    assert lookup["revtex-prl-reprint"]["extracted_format"]["heading_numbering"]["enabled"]["value"] is False
    assert lookup["revtex-aip-jmp-reprint"]["page"]["columns"] == 1


@pytest.mark.parametrize("identifier", ["elsevier-preprint-numeric", "elsevier-cas-sc", "revtex-aps-reprint", "revtex-rmp-reprint"])
def test_json_profiles_format_generic_sources_without_publisher_programs(identifier, tmp_path):
    profile = next(json.loads(p.read_text(encoding="utf-8")) for p in PROFILES if p.stem == identifier)
    source = materialize_fixture(profile, tmp_path / "source")
    before = inspect_latex(source)
    output = tmp_path / "formatted"
    report = apply_latex(source, output, profile)
    assert report["audit"]["content"] == "PASS"
    after = inspect_latex(output)
    assert before["inventory"]["main.tex"]["content_sha256"] == after["inventory"]["main.tex"]["content_sha256"]
    assert not list(output.glob("*.cls"))
    assert not list(output.glob("*.sty"))
    assert not list(output.glob("*.bst"))
    assert "{article}" in (output / "main.tex").read_text(encoding="utf-8")
