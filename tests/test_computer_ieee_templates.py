"""IEEE source bindings and materially distinct source-option formats."""
import importlib.util
import json
from pathlib import Path

import pytest
from docx import Document

from manuweave.models import StyleProfile
from manuweave.templates import validate_template
from manuweave.word import apply_docx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src/manuweave/data/templates"
FAMILY = DATA / "computer-ieee"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def profiles():
    return [read(path) for path in (FAMILY / "profiles").glob("*.json")]


def layouts():
    return read(FAMILY / "extracted-layouts.json")["layouts"]


def test_ieee_covers_each_official_journal_article_type_and_tit_alternate():
    facts = read(FAMILY / "source-facts.json")
    assert len(facts["journal_mappings"]) == 48
    assert len(facts["template_packages"]) == 12
    expected = {(j["catalog_id"], t["mapping_id"], t["template_meta"]["id"])
                for j in facts["journal_mappings"] for t in j["latex_templates"]}
    actual = {(p["journal"]["catalog_id"], p["extracted_format"]["journal_binding"]["mapping_id"],
               p["extracted_format"]["journal_binding"]["template_meta_id"]) for p in profiles()}
    assert actual == expected
    assert len(profiles()) == 52
    tit = [p for p in profiles() if p["journal"]["title"] == "IEEE Transactions on Information Theory"]
    assert {p["page"]["columns"] for p in tit} == {1, 2}
    assert {p["journal"]["stage"] for p in profiles()} == {"authoring_manuscript_template"}


def test_ieee_source_bound_names_preserve_vlsi_and_current_tcbb_title():
    mapping = read(FAMILY / "source-facts.json")["journal_mappings"]
    vlsi = next(j for j in mapping if j["abbreviation"] == "TVLSI")
    assert vlsi["selector_publication_id"] == 39
    assert {t["template_meta"]["id"] for t in vlsi["latex_templates"]} == {1, 300}
    tcbb = next(j for j in mapping if j["abbreviation"] == "TCBB")
    assert tcbb["selector_publication_name"] == "IEEE Transactions on Computational Biology and Bioinformatics"
    assert tcbb["journal_name"].startswith("IEEE/ACM ")


def test_all_ieee_rules_are_declarative_and_source_confirmed():
    old = [read(p) for p in (DATA / "ieee/profiles").glob("*.json")]
    assert len(old) == 9
    for profile in profiles() + old:
        StyleProfile.model_validate(profile, strict=True)
        validate_template(profile)
        assert profile["latex"]["documentclass"] == "article"
        assert profile["template"]["assets"] == []
        assert not profile["template"].get("fixture")
        assert all(r["checking"] == "xml" for r in profile["template"]["requirements"])
        assert len(profile["rules"]) >= 14
        assert {"captions", "equations", "references", "heading_numbering"} <= profile["extracted_format"].keys()


def test_source_measurement_values_have_units_and_provenance():
    for layout in layouts().values():
        extracted = layout["extracted_format"]
        for section in ("roles", "page", "captions", "equations", "references", "heading_numbering"):
            groups = extracted[section].values() if section == "roles" else [extracted[section]]
            for group in groups:
                for fact in group.values():
                    assert {"value", "unit", "source"} <= fact.keys()
                    assert fact["source"]["url"].startswith("https://")
                    assert fact["source"]["file"]
                    assert fact["source"]["locator"]


def test_ieee_standard_vs_cs_source_dependency_title_difference():
    data = layouts()
    standard = data["official-1-bare_jrnl_new_sample4"]
    cs = data["official-5-bare_jrnl_new_sample4"]
    assert standard["extracted_format"]["roles"]["title"]["size"]["value"] == 18
    assert cs["extracted_format"]["roles"]["title"]["size"]["value"] == 24
    assert standard["rules"]["title"]["size_pt"] == pytest.approx(18 * 72 / 72.27)
    assert cs["rules"]["title"]["size_pt"] == pytest.approx(24 * 72 / 72.27)
    assert cs["class_source"]["url"] == "https://ctan.org/pkg/ieeetran"
    assert cs["rules"]["body"]["font"] == "Times"
    assert any("omits IEEEtran.cls" in note for note in cs["coverage_notes"])


def test_tii_brief_and_research_and_vlsi_brief_source_typography():
    data = layouts()
    brief = data["official-276-tii-briefs-template"]
    research = data["official-279-tii-articles-template"]
    assert brief["rules"]["title"]["font"] == research["rules"]["title"]["font"] == "Helvetica"
    assert brief["rules"]["body"]["font"] == research["rules"]["body"]["font"] == "Times"
    assert brief["rules"]["body"]["size_pt"] == pytest.approx(9 * 72 / 72.27)
    assert research["rules"]["body"]["size_pt"] == pytest.approx(10 * 72 / 72.27)
    assert brief["extracted_format"]["roles"]["title"]["size"]["value"] == 16
    assert research["extracted_format"]["roles"]["title"]["size"]["value"] == 24
    vlsi = data["official-300-IEEE-TVLSI-brief-latex-template"]
    assert vlsi["rules"]["body"]["size_pt"] == pytest.approx(9 * 72 / 72.27)


def test_computer_society_conference_and_journal_are_different_source_modes():
    data = layouts()
    journal = data["old-ieee-journal-compsoc"]
    conference = data["old-ieee-conference-compsoc"]
    assert journal["rules"]["body"]["font"] == "Palatino"
    assert journal["rules"]["body"]["size_pt"] == pytest.approx(9.5, abs=0.0001)
    assert conference["rules"]["body"]["font"] == "Times"
    assert conference["rules"]["body"]["size_pt"] == pytest.approx(10, abs=0.0001)
    assert conference["rules"]["title"]["size_pt"] == pytest.approx(14, abs=0.0001)


def test_natural_baselines_and_table_struts_are_not_claimed_as_exact():
    for layout in layouts().values():
        for rule in layout["rules"].values():
            assert rule.get("line_spacing_rule") in {None, "atLeast"}
            assert rule.get("line_spacing_pt", 1) > 0
        strut = layout["extracted_format"]["captions"]["table_rowheight"]
        assert float(strut["value"].removesuffix("pt")) > 0
    tmi = layouts()["official-147-main"]
    assert "missing stretch number" in tmi["extracted_format"]["references"]["source_defect"]["value"]
    assert tmi["rules"]["reference"]["font"] == "Times"
    assert tmi["extracted_format"]["roles"]["reference"]["size"]["value"] == 8


def test_full_width_frontmatter_starts_columns_at_the_native_boundary():
    data = layouts()
    assert data["official-1-bare_jrnl_new_sample4"]["sections"]["body_starts_at"] == "first_abstract"
    for mode in ["old-ieee-journal-compsoc", "old-ieee-journal-transmag", "old-ieee-peerreview", "old-ieee-peerreviewca"]:
        assert data[mode]["sections"]["body_starts_at"] == "first_heading1"
    assert data["old-ieee-technote"]["sections"] is None
    assert data["official-281-one-column"]["sections"] is None


def test_ieee_builder_works_entirely_from_checked_in_json():
    spec = importlib.util.spec_from_file_location("ieee_builder", ROOT / "scripts/build_computer_ieee_profiles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = {p.name: p.read_bytes() for p in (FAMILY / "profiles").glob("*.json")}
    assert len(module.build()) == 52
    assert before == {p.name: p.read_bytes() for p in (FAMILY / "profiles").glob("*.json")}


def test_ieee_minimum_baseline_and_halfpoint_word_projection(tmp_path):
    profile = next(p for p in profiles() if p["extracted_format"]["mode"] == "official-276-tii-briefs-template")
    document = Document()
    for text in ["Synthetic title", "Synthetic author", "Synthetic affiliation", "Abstract: synthetic abstract", "Keywords: synthetic", "1 Introduction", "Synthetic body", "Figure 1 Synthetic caption", "Table 1 Synthetic caption", "[1] Synthetic reference"]:
        document.add_paragraph(text)
    source, output = tmp_path / "source.docx", tmp_path / "output.docx"
    document.save(source)
    roles = {f"p{i}": role for i, role in enumerate(["title", "author", "affiliation", "abstract", "keywords", "heading1", "body", "figure_caption", "table_caption", "reference"])}
    audit = apply_docx(source, output, profile, roles)["audit"]
    assert audit["content"]["status"] == "PASS"
    assert audit["style"]["status"] == "PASS"
    assert audit["style"]["exact_source_sizes"] is False
    assert audit["style"]["representation_adjustments"]
