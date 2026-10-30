"""Generate only the Wiley computer-journal rules established by pinned facts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "src" / "manuweave" / "data" / "templates" / "computer-wiley"


def measured(value, unit, source, locator, condition=None):
    origin = {key: source[key] for key in ("url", "file", "sha256", "source_version", "archive_sha256") if key in source}
    related = source.get("related_files", {})
    mentioned = locator.split(":", 1)[0]
    if mentioned in related:
        origin.update(file=mentioned, sha256=related[mentioned])
    origin["locator"] = locator
    result = {"value": value, "unit": unit, "source": origin}
    if condition:
        result["condition"] = condition
    if unit == "tex_pt":
        result["physical_word_pt"] = value * 72 / 72.27
    return result


def njd_format(source):
    """Facts from USG 6.0's explicit two-column branches, not executable code."""
    roles = {}

    def role(name, size, baseline, locator, *, unit="tex_pt", bold=None, alignment=None):
        properties = {"font": measured("STIX Two Text", None, source, "USG.cls:335-337, stix2 text family"),
                      "size_pt": measured(size, unit, source, locator),
                      "line_spacing_pt": measured(baseline, unit, source, locator)}
        if bold is not None:
            properties["bold"] = measured(bold, None, source, locator)
        if alignment:
            properties["alignment"] = measured(alignment, None, source, locator)
        roles[name] = properties

    role("title", 18, 21, "USG.cls:886, titlefont in two-column branch", bold=True, alignment="left")
    role("subtitle", 16, 21, "USG.cls:887, subtitlefont in two-column branch", bold=True, alignment="left")
    role("author", 9, 12, "USG.cls:888, Authorfont", alignment="left")
    role("affiliation", 7.5, 10, "USG.cls:930, addressfont")
    role("correspondence", 7.5, 10, "USG.cls:931, corresfont", alignment="left")
    role("abstract", 9, 13, "USG.cls:935 and 1382-1398, abstractfont in abstract box")
    role("abstract_heading", 10, 15, "USG.cls:889 and 1396, absheadfont", bold=True)
    role("heading1", 10, 12, "USG.cls:1671, final section definition in two-column branch", bold=True)
    role("heading2", 10, 12, "USG.cls:1672, final subsection definition in two-column branch", bold=True)
    role("heading3", 9, 11, "USG.cls:1673, final subsubsection definition", bold=True)
    role("heading4", 9, 11, "USG.cls:1674, paragraph run-in definition", bold=True)
    role("heading5", 9, 11, "USG.cls:1675, subparagraph run-in definition", bold=True)
    role("body", 9, 11.5, "USG.cls:716-726, normalsize two-column branch", unit="bp")
    # 13bp is assigned at class-load time, while invoking normalsize selects
    # 11.5bp. Retain both established facts without guessing the final context.
    roles["body"]["line_spacing_pt"]["condition"] = "When the source normalsize macro is invoked; load-time baseline is separately 13bp."
    roles["body"]["load_time_baseline_pt"] = measured(13, "bp", source, "USG.cls:725-726", "At class-load time")
    roles["body"]["first_line_pt"] = measured(9, "bp", source, "USG.cls:397-420; paragraph indent 1em with 9bp normal text")
    roles["body"]["space_after_pt"] = measured(0, "bp", source, "USG.cls:420, paragraph skip zero")
    role("caption", 8, 10, "USG.cls:361-370, active general caption formatter")
    roles["caption"]["label_bold"] = measured(True, None, source, "USG.cls:363-366")
    role("table_body", 8.5, 11.5, "USG.cls:916, tablebodyfont", unit="bp")
    roles["table_body"]["header_bold"] = measured(True, None, source, "USG.cls:917, tablecolheadfont")
    role("reference", 8.5, 11.5, "USG.cls:925, reflistfont", unit="tex_pt")
    roles["reference"]["size_pt"]["condition"] = "When reflistfont is selected; APA-specific refapasize is separately 8.5/11 TeXpt."
    roles["reference"]["line_spacing_pt"]["condition"] = roles["reference"]["size_pt"]["condition"]
    roles["reference"]["apa_baseline_pt"] = measured(11, "tex_pt", source, "USG.cls:760, refapasize", "APA reference-size macro")
    for name, before in (("heading1", 27), ("heading2", 23), ("heading3", 20), ("heading4", 12), ("heading5", 10)):
        roles[name]["space_before_pt"] = measured(before, "bp", source, "USG.cls:1671-1675; absolute before-skip magnitude")
        roles[name]["space_after_pt"] = measured(8 if name in {"heading1", "heading2", "heading3"} else 0, "bp", source,
            "USG.cls:1671-1675", "For levels 4 and 5, run-in composition requires host layout support.")
    page = {key: measured(value, "mm" if key != "columns" else None, source, "USG.cls:376-393; two-column choice in original sample line 1")
            for key, value in {"width_mm": 210, "height_mm": 276, "margin_left_mm": 16, "margin_right_mm": 16,
                               "margin_top_mm": 12, "margin_bottom_mm": 30, "column_gap_mm": 6, "columns": 2}.items()}
    return {"mode": "source_template_two_column_choice", "source_configuration": {"columns": 2, "exactsize_override": False},
            "roles": roles, "page": page,
            "citations": {"available_reference_modes": measured(["APA", "AMS", "AMA", "Vancouver", "Chemistry", "Harvard", "Chicago", "MPS", "APS", "MLA"], None,
                source, "USG.cls:59-85 and reference-style conditionals:1920-2120")},
            "special_layout": {"abstract_box_padding_mm": measured(3.5, "mm", source, "USG.cls:1385-1393"),
                "abstract_box_border_pt": measured(0, "bp", source, "USG.cls:1391-1393")},
            "limitations": ["Run-in level 4/5 headings, mixed caption labels and special title/abstract boxes retain explicit source facts but need contextual host layout handling.",
                "The 13bp class-load body baseline and 11.5bp normalsize baseline are distinct contexts; neither is silently treated as a universal fixed body baseline.",
                "Raw TeX pt differs from physical Word pt/bp. Shared rules retain exact physical values; only the Word writer quantizes them to OOXML half-points and reports that representation adjustment."]}


def cgf_format(source):
    roles = {}
    for name, size, line, locator, bold, italic, align in [
        ("title", 20, 25, "egpubl.cls:186,753-762, huge bold title", True, False, "center"),
        ("author", 9, 11, "egpubl.cls:154,758-760", False, False, "center"),
        ("affiliation", 8, 10, "egpubl.cls:163 and 779-784, author next line", False, False, "center"),
        ("body", 9, 11, "egpubl.cls:154-161", False, False, "justify"),
        ("abstract", 9, 11, "egpubl.cls:793-806; normal text inherited, italic body", False, True, "justify"),
        ("heading1", 9, 11, "egpubl.cls:348-351", True, False, "left"),
        ("heading2", 9, 11, "egpubl.cls:352-355", True, False, "left"),
        ("heading3", 9, 11, "egpubl.cls:356-359", True, False, "left"),
        ("caption", 9, 11, "egpubl.cls:310-317; normal size inherited", None, None, None),
        ("reference", 8, 9, "egpubl.cls:1994-2006", False, False, "justify"),
    ]:
        role = {"font": measured("Times", None, source, "dfadobe.sty:9-14; ptm Times family"),
                "size_pt": measured(size, "tex_pt", source, locator), "line_spacing_pt": measured(line, "tex_pt", source, locator)}
        for key, value in (("bold", bold), ("italic", italic), ("alignment", align)):
            if value is not None:
                role[key] = measured(value, None, source, locator)
        roles[name] = role
    roles["body"]["first_line_pt"] = measured(9, "tex_pt", source, "egpubl.cls:257-258; 1em at 9TeXpt")
    roles["body"]["space_after_pt"] = measured(5.5, "tex_pt", source, "egpubl.cls:257; natural paragraph skip, stretch/shrink separately 1/-1.5pt")
    roles["abstract"]["left_indent_pt"] = measured(24, "tex_pt", source, "egpubl.cls:805; 2pc")
    roles["abstract"]["right_indent_pt"] = measured(24, "tex_pt", source, "egpubl.cls:805; 2pc")
    roles["caption"]["label_bold"] = measured(True, None, source, "egpubl.cls:310-315")
    roles["caption"]["text_italic"] = measured(True, None, source, "egpubl.cls:310-315")
    roles["caption"]["alignment_condition"] = measured("center when one line; paragraph layout otherwise", None, source, "egpubl.cls:312-315")
    for name, before in (("heading1", 11), ("heading2", 11), ("heading3", 5.5)):
        roles[name]["space_before_pt"] = measured(before, "tex_pt", source, "egpubl.cls:348-359; before-skip natural magnitude")
        roles[name]["space_after_pt"] = measured(0.001, "tex_pt", source, "egpubl.cls:350,354,358")
    factor = 25.4 / 72.27
    left, width, top, height = (72.27 - 23) * factor, 504 * factor, (72.27 - 12 + 11 + 11) * factor, 636 * factor
    page = {key: measured(value, "mm" if key != "columns" else None, source, "egpubl.cls:135-219; paper size measured from original EGauthorGuidelines-cgf-sub.pdf MediaBox")
            for key, value in {"width_mm": 210, "height_mm": 297, "columns": 2, "margin_left_mm": left,
                "margin_right_mm": 210 - left - width, "margin_top_mm": top, "margin_bottom_mm": 297 - top - height,
                "column_gap_mm": 24 * factor}.items()}
    return {"mode": "cgf_regular_issue_submission", "roles": roles, "page": page,
            "citations": {"bibliography_style": measured("eg-alpha-doi", None, source, "EGauthorGuidelines-body-sub.inc:469"),
                          "reference_hanging_indent_pt": measured(8, "tex_pt", source, "egpubl.cls:1998-2000; 1em at 8TeXpt")},
            "limitations": ["This is the regular-issue submission format, not a conference-specific special-issue style.",
                "The journal source has full-width title/abstract composition, context-sensitive captions and flexible TeX skips; the Word projection covers explicit scalar properties and records these contextual details.",
                "Paper size comes from the supplied official PDF; margins combine its A4 box with the class text-box dimensions and standard 1in TeX origin."]}


def word_projection(extracted):
    supported = {"font", "size_pt", "bold", "italic", "alignment", "first_line_pt", "space_before_pt", "space_after_pt", "line_spacing_pt"}
    rules = {}
    for name, properties in extracted["roles"].items():
        rule = {}
        for key, record in properties.items():
            if key not in supported or record.get("condition"):
                continue
            value = record["value"]
            if record["unit"] == "tex_pt":
                value *= 72 / 72.27
            rule[key] = value
        if "line_spacing_pt" in rule:
            rule["line_spacing_rule"] = "exact"
        rules[name] = rule
    return rules, {key: record["value"] for key, record in extracted["page"].items()}


def detailed_profile(identifier, name, extracted, source, binding, reference_style=None, optional=False):
    rules, page = word_projection(extracted)
    if reference_style:
        extracted["citations"]["journal_reference_family"] = measured(reference_style, None, binding, "Journal-specific Reference Style section")
    requirements = []
    for target, properties in [*rules.items(), ("page", page)]:
        for key, value in properties.items():
            requirements.append(requirement(f"{target}-{key}".replace("_", "-"), target, key, value, source,
                "See extracted_format corresponding role/page property and its pinned source locator",
                detail="Exact physical-unit conversion of the recorded source value. The shared rule is not quantized; the Word writer reports any OOXML half-point representation adjustment. This scalar rule does not assert exact TeX flexible-skip behavior."))
    if reference_style:
        requirements.append(requirement("journal-reference-family", "reference", "citation_style", reference_style, binding,
                            "Journal-specific Reference Style section", checking="host",
                            detail="An explicit family, not an invented edition; initial free-format exceptions still apply."))
    mode = "optional journal-recommended NJD template choice" if optional else "source-established journal layout"
    item = profile(identifier, name, mode + "; JSON typography and geometry only; no publisher source file is installed or executed.",
                   [name], rules, page, source, requirements,
                   extracted["limitations"] + ["Font availability and actual rendering require independent checks.",
                    "No class/options payload stands in for missing typography; extracted_format records the actual numeric source declarations."])
    item["extracted_format"] = extracted
    item["sources"].append({key: value for key, value in binding.items() if key != "facts"})
    item["journal_binding"] = {"name": binding["journal"], "source_url": binding["url"],
                               "strength": "recommended_optional_choice" if optional else "source_established_layout"}
    return item


def requirement(identifier, target, prop, expected, source, locator, *, checking="xml", detail=""):
    return {
        "id": identifier, "category": "typography" if checking == "xml" else "references",
        "target": target, "property": prop, "expected": expected,
        "unit": "pt" if prop.endswith("_pt") else "mm" if prop.endswith("_mm") else None,
        "source": {"url": source["url"], "file": source["file"], "locator": locator},
        "certainty": "verified", "checking": checking, "applies_to": ["docx"], "detail": detail,
    }


def profile(identifier, name, scope, aliases, rules, page, source, requirements, notes):
    return {
        "id": identifier, "name": name, "version": "1.0.0", "scope": scope, "aliases": aliases,
        "compliance": "source_backed_template_partial_coverage", "rules": rules, "page": page, "latex": {},
        "sources": [{key: value for key, value in source.items() if key != "facts"}],
        "template": {
            "family": "computer-wiley", "source_version": source.get("source_version", source.get("retrieved", "2026-10-30") + " pinned source"),
            "license": "ManuWeave rule encoding is MIT; factual configuration only; no publisher source software redistributed",
            "source_url": source["url"], "assets": [],
            "engine_support": {"docx": "partial", "latex": "unsupported"},
            "requirements": requirements, "coverage_notes": notes,
        },
    }


def build():
    facts = json.loads((ROOT / "source-facts.json").read_text(encoding="utf-8"))
    sources = {source["id"]: source for source in facts["sources"]}
    spe = sources["spe-guide"]
    locator = "MANUSCRIPT STYLE: " + spe["facts"]["manuscript_style"]
    rules = {"body": {"font": "Times", "size_pt": 12, "line_spacing": 1}}
    page = {"columns": 1}
    requirements = [requirement("body-" + key, "body", key, value, spe, locator,
                    detail="The source calls this preferred typography. Times is selected from its explicit allowed font list; no font substitution is authorized.")
                    for key, value in rules["body"].items()]
    requirements.append(requirement("page-columns", "page", "columns", 1, spe, locator))
    requirements.append(requirement("reference-style", "reference", "citation_style", "AMA", spe,
                        "REFERENCE STYLE: AMA - American Medical Association", checking="host",
                        detail="This is the named reference-style section. Initial free-format submission separately permits any consistent reference style; the host must respect that stage and must not invent or replace references."))
    requirements.append(requirement("reference-sequence", "reference", "numbering_order", "order_of_appearance", spe,
                        "REFERENCE STYLE: numbered consecutively in order of appearance; Arabic superscript in-text numerals", checking="host"))
    profiles = [profile("computer-wiley-spe-manuscript", "Software: Practice and Experience — source-stated manuscript typography",
                "Preferred manuscript typography from the SPE author guide. Partial editable Word coverage; this does not reproduce a final Wiley publication design.",
                ["SPE manuscript typography", "Software Practice and Experience manuscript"], rules, page, spe, requirements,
                ["Applies only the explicit preferred body font, body size, single line spacing and single-column settings.",
                 "Times, Helvetica and Courier are alternatives in the source. This profile selects Times literally; missing local Times requires a reported font failure or an explicitly source-permitted host choice.",
                 "Reference formatting requires host review; initial free-format and later reference-style instructions retain their distinct stages.",
                 "No page dimensions, margins, title sizes, heading sizes or table borders are inferred.",
                 "No publisher class is redistributed and native LaTeX formatting is unsupported by this profile."])]
    jasist = sources["wiley-2025-journal-mapping"]
    row = jasist["facts"]["row"]
    locator = f"Sheet1, row {row}; exact journal title in column A; B reference style, C column count, D typography, E layout size"
    rules = {"body": {"font": "STIX Two Text"}}
    page = {"columns": 2, "width_mm": 210, "height_mm": 276}
    requirements = [requirement("body-font", "body", "font", "STIX Two Text", jasist, locator,
                    detail="The journal-specific row specifies stixtwotext, the STIX Two Text family. No Times replacement is authorized.")]
    requirements += [requirement("page-" + key, "page", key, value, jasist, locator) for key, value in page.items()]
    requirements.append(requirement("reference-style", "reference", "citation_style", "APA", jasist, locator, checking="host",
                        detail="The source identifies APA reference style without an edition number. An APA edition is not inferred and host review must retain real cited sources."))
    profiles.append(profile("computer-wiley-jasist-njd-2025", "JASIST — Wiley 2025 journal-specific NJD layout mapping",
                    "JASIST's explicit row in the official Wiley 2025 NJD journal list: STIX Two Text, two columns, L3 210 × 276 mm and APA references. Partial Word layout coverage only.",
                    ["JASIST NJD 2025", "JASIST Wiley source layout"], rules, page, jasist, requirements,
                    ["The 2025 row establishes journal-specific font, columns, dimensions and reference family.",
                     "The row gives no body font size, heading typography, margin dimensions or line spacing; these are not invented.",
                     "APA edition and actual citation transformation require host review; the local Word engine does not fabricate bibliography entries.",
                     "No Wiley source class is redistributed; native LaTeX formatting is unsupported by this profile."]))
    # Detailed numerical source extraction supersedes the earlier shallow
    # JASIST mapping while retaining its stable public identifier.
    profiles = [item for item in profiles if item["id"] != "computer-wiley-jasist-njd-2025"]
    spe_extracted = {"mode": "source_stated_preferred_manuscript_typography", "roles": {"body": {
        key: measured(value, "pt" if key == "size_pt" else None, spe, locator)
        for key, value in profiles[0]["rules"]["body"].items()}}, "page": {
        "columns": measured(1, None, spe, locator)}, "citations": {
        "reference_style_after_free_format_stage": measured("AMA", None, spe, "REFERENCE STYLE section"),
        "initial_submission_any_consistent_style": measured(True, None, spe, "Free format submission section")}}
    profiles[0]["extracted_format"] = spe_extracted
    profiles[0]["journal_binding"] = {"name": "Software: Practice and Experience", "source_url": spe["url"], "strength": "preferred"}
    for item in facts["declarative_profiles"]:
        source = sources["njd-format" if item["format"] == "njd" else "cgf-format"]
        extracted = njd_format(source) if item["format"] == "njd" else cgf_format(source)
        profiles.append(detailed_profile(item["id"], item["name"], extracted, source, item["binding"],
                        item["binding"].get("reference_style"), item["optional"]))
    for item in facts["direct_manuscript_profiles"]:
        binding = item["binding"]
        values = {"font": "Times", "size_pt": 12}
        locator = "MANUSCRIPT STYLE: 12-point type in standard fonts Times, Helvetica or Courier is preferred; double-line spacing is not necessary."
        requirements = [requirement("body-" + key, "body", key, value, binding, locator) for key, value in values.items()]
        result = profile(item["id"], binding["journal"] + " — explicit preferred manuscript typography",
                        "Only the journal guide's explicit preferred 12-point font setting; no missing title, margin or column requirement is invented.",
                        [binding["journal"] + " preferred manuscript"], {"body": values}, {}, binding, requirements,
                        ["Times is selected literally from the allowed source fonts.",
                         "Not necessary to double-line space is not converted into a mandatory single-spacing value.",
                         "A separate optional NJD design choice supplies source-extracted typography when explicitly selected."])
        result["journal_binding"] = {"name": binding["journal"], "source_url": binding["url"], "strength": "preferred"}
        result["extracted_format"] = {"mode": "source_stated_preferred_manuscript_typography",
                "roles": {"body": {key: measured(value, "pt" if key == "size_pt" else None, binding, locator)
                                   for key, value in values.items()}}, "page": {}, "citations": {}}
        profiles.append(result)
    destination = ROOT / "profiles"
    destination.mkdir(exist_ok=True)
    catalog = json.loads((ROOT.parent / "computer-catalog.json").read_text(encoding="utf-8"))
    names = {}
    for journal in catalog["journals"]:
        names.setdefault(journal["name"], []).append(journal["id"])
    for item in profiles:
        journal_name = item["journal_binding"]["name"]
        matches = names.get(journal_name, [])
        if len(matches) != 1:
            raise ValueError(f"Expected one exact computer-catalog title match for {journal_name!r}")
        item["catalog_ids"] = matches
        (destination / (item["id"] + ".json")).write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return profiles


if __name__ == "__main__":
    build()
