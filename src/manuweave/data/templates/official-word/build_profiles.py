"""Rebuild fact-derived profiles from the captured official-template observations.

No template prose is redistributed. ``source-facts.json`` contains measured
style/section values and provenance, captured from the pinned source documents.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALIGN = {0: "left", 1: "center", 2: "right", 3: "justify"}


def _format(observation):
    result = {key: observation[key] for key in (
        "font", "size_pt", "space_before_pt", "space_after_pt", "first_line_pt", "left_indent_pt"
    ) if key in observation}
    for flag in ("bold", "italic"):
        result[flag] = observation[flag] == -1
    result["alignment"] = ALIGN[observation["paragraph_alignment"]]
    rule = observation["line_rule"]
    if rule == 0:
        result.update(line_spacing_rule="auto", line_spacing=1.0)
    elif rule == 5:
        result.update(line_spacing_rule="auto", line_spacing=round(observation["line_spacing_pt"] / 12, 6))
    elif rule in {3, 4}:
        result.update(line_spacing_rule={3: "atLeast", 4: "exact"}[rule],
                      line_spacing_pt=round(observation["line_spacing_pt"], 4))
    return {key: round(value, 4) if isinstance(value, float) else value for key, value in result.items()}


def build():
    facts = json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    for source_id, fact in facts["documents"].items():
        ieee = source_id.startswith("ieee")
        mapping = ({"title": "paper title", "body": "Body Text", "heading1": "heading 1",
                    "heading2": "heading 2", "heading3": "heading 3", "heading4": "heading 4",
                    "references_heading": "heading 5", "abstract": "Abstract", "keywords": "Keywords",
                    "figure_caption": "figure caption", "table_caption": "table head", "reference": "references"}
                   if ieee else
                   {"title": "Title_document", "body": "Para", "heading1": "Head1", "heading2": "Head2",
                    "heading3": "Head3", "abstract": "Abstract", "keywords": "KeyWords",
                    "figure_caption": "FigureCaption", "table_caption": "TableCaption",
                    "reference": "Bib_entry", "equation": "DisplayFormula", "table_body": "TableCell"})
        rules = {role: _format(fact["styles"][name]) for role, name in mapping.items()}
        requirements = []

        def requirement(identity, category, target, prop, expected, source_locator, *, checking="host", certainty="verified", detail="", unit=None):
            requirements.append({"id": identity, "category": category, "target": target,
                                 "property": prop, "expected": expected, "unit": unit,
                                 "source": {"url": fact["url"], "file": fact["source_filename"], "locator": source_locator},
                                 "certainty": certainty, "checking": checking, "applies_to": ["docx"], "detail": detail})

        for role, props in rules.items():
            style_name = mapping[role]
            locator = fact["style_locators"][style_name]
            for key, value in props.items():
                property_locator = fact.get("property_locators", {}).get(style_name + "." + key, locator)
                requirement(f"{role}-{key}", "typography", role, key, value, property_locator,
                            checking="xml", unit="pt" if key.endswith("_pt") else None,
                            detail="Measured style definition, with inherited defaults resolved by read-only Microsoft Word; instructional run emphasis is excluded.")
        for key, value in fact["body_page"].items():
            requirement(f"page-{key}", "layout", "page", key, value, fact["body_section_locator"],
                        checking="xml", unit="mm" if key.endswith("_mm") else None,
                        detail="Main-text section only; title and author sections have distinct native layouts.")
        if ieee:
            guide = fact["guidance_locators"]
            requirement("reference-citation-style", "citation", "document", "citation_style", "numeric_square_brackets",
                        guide["consecutive_citations"], detail="Reference numbers appear consecutively in square brackets; punctuation follows the bracket.")
            requirement("reference-citation-order", "citation", "document", "citation_numbering", "consecutive",
                        guide["consecutive_citations"], detail="The source explicitly requires consecutive numbering. Venue-specific bibliography sorting still needs the reference guide.")
            requirement("forbid-page-numbers", "pagination", "document", "page_numbers_allowed", False,
                        guide["no_pagination"], checking="xml", detail="This pinned conference template instructs authors not to add pagination.")
            requirement("abstract-no-footnotes", "content_policy", "abstract", "footnotes_allowed", False,
                        guide["no_abstract_footnotes"])
            requirement("reference-no-footnotes", "content_policy", "reference", "footnotes_allowed", False,
                        guide["no_abstract_footnotes"])
            requirement("title-no-math", "content_policy", "title", "math_allowed", False,
                        guide["title_abstract_restrictions"])
            requirement("abstract-no-math", "content_policy", "abstract", "math_allowed", False,
                        guide["title_abstract_restrictions"])
            requirement("title-no-subtitle", "structure", "title", "subtitle_allowed", False,
                        guide["no_subtitle"], detail="The template states that subtitles are not captured in Xplore.")
            requirement("figure-caption-below", "caption", "figure_caption", "position", "below_object",
                        guide["figure_table_position"])
            requirement("table-caption-above", "caption", "table_caption", "position", "above_object",
                        guide["figure_table_position"])
            requirement("equation-numbering", "numbering", "equation", "numbering", "consecutive_parenthesized_right",
                        guide["equation_numbers"])
            for key, identity, category, prop in (
                ("heading1_small_caps", "heading1-small-caps", "typography", "small_caps"),
                ("heading1_numbering", "heading-numbering", "numbering", "numbering"),
            ):
                observed = fact.get("xml_observations", {}).get(key)
                if observed is not None:
                    if observed["source_sha256"] != fact["sha256"]:
                        raise ValueError("Original XML observation does not match the pinned source")
                    requirement(identity, category, "heading1", prop, observed["value"], observed["locator"],
                                detail="Confirmed directly in the SHA-matched original Strict OOXML.")
            requirement("reference-hanging-indent", "typography", "reference", "hanging_indent_pt",
                        -fact["styles"]["references"]["first_line_pt"],
                        fact["numbering_locator"], unit="pt", detail="The reference list's native numbering definition supplies a hanging indent.")
        else:
            guide = fact["guidance_locators"]
            requirement("single-column-review", "layout", "document", "columns", 1, guide["one_column"])
            requirement("no-running-text", "pagination", "document", "headers_footers_allowed", False,
                        guide["one_column"], checking="xml", detail="The review submission source excludes running headers and footers; accepted-publication output uses the TAPS workflow.")
            requirement("citation-venue-selection", "citation", "document", "citation_style", ["numeric", "author_year"],
                        guide["citation_options"], certainty="conditional",
                        detail="The source permits numbered and author-year placeholders; the selected venue decides which style applies. Do not force numeric citations for every ACM venue.")
            requirement("double-blind-identity", "review_policy", "document", "author_identifying_content_allowed", False,
                        guide["double_blind"], certainty="conditional",
                        detail="Only when the venue uses double-blind review: omit author identity and identifying acknowledgments, citations or related-work discussion. This is not a blanket citation ban.")
            requirement("double-blind-metadata", "review_policy", "metadata", "author_identity_allowed", False,
                        guide["anonymous_metadata"], certainty="conditional")
            requirement("native-table-not-image", "accessibility", "table", "rasterized_table_allowed", False,
                        guide["native_tables"])
            requirement("table-caption-above", "caption", "table_caption", "position", "above_object",
                        guide["table_caption"])
            requirement("figure-after-first-reference", "caption", "image", "position", "after_first_reference",
                        guide["figure_caption"])
            requirement("figure-alternative-description", "accessibility", "image", "alternative_description_required", True,
                        guide["figure_description"], detail="The source contains an unresolved 'xxx characters' placeholder; no numeric character limit is invented.")
            requirement("reference-not-table", "structure", "reference", "inside_table_allowed", False,
                        guide["references_not_table"], checking="xml")
            requirement("native-word-equations", "equation", "equation", "native_equation_editor", True,
                        guide["native_equations"], checking="xml")
            requirement("document-language-metadata", "accessibility", "metadata", "language_required", True,
                        guide["language_metadata"])
            requirement("first-body-paragraph-indent", "typography", "body", "post_heading_first_line_pt",
                        fact["styles"]["PostHeadPara"]["first_line_pt"],
                        fact["style_locators"]["PostHeadPara"], certainty="conditional", unit="pt",
                        detail="The first paragraph after a heading uses PostHeadPara; later body paragraphs use Para with a 12pt first-line indent.")
        profile = {
            "id": source_id, "name": fact["name"], "version": "1.0.0", "scope": fact["scope"],
            "aliases": fact["aliases"], "compliance": "source_backed_template_partial_coverage",
            "rules": rules, "page": copy.deepcopy(fact["body_page"]), "latex": {},
            "sources": [{"url": fact["url"], "title": fact["name"], "sha256": fact["sha256"],
                         "retrieved_at": "2026-10-30", "source_modified": fact["source_modified"],
                         "source_verified": True, "submission_compliance_verified": False,
                         "original_file_redistributed": False, "provenance": fact["provenance"]}],
            "checks": [{"role": r, "property": p, "expected": v} for r, props in rules.items() for p, v in props.items()],
            "examples": [{"kind": "synthetic_docx", "generator": "tests/test_official_word_templates.py", "profile": source_id}],
            "template": {"family": "IEEE conference Word" if ieee else "ACM Word submission",
                         "source_version": fact["source_modified"], "license": "rules_only_source_not_redistributed",
                         "source_url": fact["url"], "assets": [], "engine_support": {"docx": "partial", "latex": "unsupported"},
                         "requirements": requirements,
                         "coverage_notes": fact["coverage_notes"] + [
                             "Typography and main-text page attributes derive from the pinned Word source; semantic policies retain their source-defined scope.",
                             "This fixed source version is not a claim of current compliance with every venue using the publisher's name."]}}
        (HERE / "profiles" / (source_id + ".json")).write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
