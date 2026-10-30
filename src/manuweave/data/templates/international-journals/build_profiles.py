"""Build explicitly scoped journal Word profiles from verified official facts.

`--refresh` fetches only the fixed official URLs below, verifies every fact's
source anchor and records actual response hashes. No source HTML is saved.
Normal execution rebuilds profiles from the already pinned source-facts file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lxml import html

HERE = Path(__file__).resolve().parent
DATE = "2026-10-30"
URLS = {
    "plos-one": "https://journals.plos.org/plosone/s/submission-guidelines",
    "plos-comp-biol": "https://journals.plos.org/ploscompbiol/s/submission-guidelines",
    "bmc-main": "https://link.springer.com/journal/12889/submission-guidelines",
    "bmc-research": "https://link.springer.com/journal/12889/submission-guidelines/research-article",
    "frontiers-public-health": "https://www.frontiersin.org/journals/public-health/for-authors/author-guidelines",
}
ROLES = ["title", "body", "abstract_heading", "abstract", "keywords", "heading1", "heading2", "heading3",
         "caption", "figure_caption", "table_caption", "table_body", "reference", "references_heading", "equation"]


def policy(identity, category, target, prop, expected, source, anchor, detail, checking="host", unit=None):
    return {"id": identity, "category": category, "target": target, "property": prop, "expected": expected,
            "source_key": source, "anchor": anchor, "detail": detail, "checking": checking,
            "certainty": "verified", "unit": unit}


def plos_common(source):
    return [
        policy("font-choice", "typography", "body", "font_choice", {"fixed_family": False, "fixed_size": False, "forbidden_family": "Symbol"}, source,
               "Use a standard font size and any standard font", "The guide allows standard font families and sizes, with Symbol excluded. The profile does not invent a fixed font or point size."),
        policy("heading-depth", "structure", "document", "maximum_heading_levels", 3, source,
               "Limit manuscript sections and sub-sections to 3 heading levels", "Keep the manuscript hierarchy within three heading levels."),
        policy("page-numbering", "layout", "document", "page_numbers_required", True, source,
               "Include page numbers and line numbers", "Include page and line numbering in the submitted manuscript."),
        policy("continuous-line-numbering", "layout", "document", "line_numbering", "continuous", source,
               "Use continuous line numbers", "Line numbering continues across pages rather than restarting on each page."),
        policy("footnotes", "structure", "document", "footnotes_allowed", False, source,
               "Footnotes are not permitted", "Move footnote information only after reviewing its meaning; formatting must not silently delete it."),
        policy("reference-style", "citation", "reference", "bibliography_style", "Vancouver", source,
               "Vancouver", "The journal specifies Vancouver reference formatting; this partial Word profile records the policy without rewriting references automatically."),
        policy("figure-caption-position", "layout", "figure_caption", "placement", "after_first_citing_paragraph", source,
               "immediately following the paragraph", "Place figure captions after the first paragraph that cites the figure; upload figure files separately."),
    ]


def definitions():
    one = plos_common("plos-one") + [
        policy("abstract-limit", "structure", "abstract", "maximum_words", 300, "plos-one", "Not exceed 300 words", "The abstract must not exceed 300 words.", unit="words"),
        policy("abstract-citations", "citation", "abstract", "citations_allowed", False, "plos-one", "Abstracts should not include", "The abstract excludes citations."),
        policy("author-title-page", "identity", "title_page", "author_names_and_affiliations_required", True, "plos-one",
               "Title page: List title, authors, and affiliations", "The first manuscript page identifies authors and affiliations. This profile does not anonymize author identities."),
        policy("table-position", "layout", "table", "placement", "after_first_citing_paragraph", "plos-one",
               "Tables are inserted immediately after", "Insert a table after the first paragraph citing it."),
    ]
    comp = plos_common("plos-comp-biol") + [
        policy("abstract-limit", "structure", "abstract", "maximum_words", 300, "plos-comp-biol", "it must not exceed 300 words", "The abstract has a 300-word maximum.", unit="words"),
        policy("abstract-citations", "citation", "abstract", "citations_allowed", False, "plos-comp-biol", "Do not include any citations", "The abstract excludes citations."),
        policy("abstract-subheadings", "structure", "abstract", "subheadings_allowed", False, "plos-comp-biol",
               "do not apply these distinct headings to the Abstract", "The abstract has conceptual components but does not display the component headings."),
        policy("author-summary", "structure", "author_summary", "word_range", [150, 200], "plos-comp-biol",
               "150-200 word non-technical summary", "Research articles include a separate nontechnical Author Summary immediately after the abstract.", unit="words"),
        policy("author-title-page", "identity", "title_page", "author_names_and_affiliations_required", True, "plos-comp-biol",
               "Enter author names on the title page", "Identify authors and affiliations on the title page rather than removing them automatically."),
    ]
    bmc = [
        policy("page-and-line-numbers", "layout", "document", "page_and_line_numbers_required", True, "bmc-main",
               "Include line and page numbering", "The main manuscript includes both line and page numbering."),
        policy("no-manual-page-breaks", "layout", "document", "manual_page_breaks_allowed", False, "bmc-main",
               "Do not use page breaks in your manuscript", "Do not add manual page breaks as a formatting shortcut."),
        policy("abstract-limit", "structure", "abstract", "maximum_words", 350, "bmc-research",
               "The Abstract should not exceed 350 words", "Research-article abstracts have a maximum of 350 words.", unit="words"),
        policy("abstract-structure", "structure", "abstract", "required_labels", ["Background", "Methods", "Results", "Conclusions"], "bmc-research",
               "The abstract must include the following separate sections", "Use the research-article abstract labels specified by the journal. Trial-registration information is additionally required for applicable intervention trials."),
        policy("abstract-citations", "citation", "abstract", "citations_allowed", False, "bmc-research",
               "do not cite references in the abstract", "Do not cite references in the abstract."),
        policy("keyword-count", "structure", "keywords", "count_range", [3, 10], "bmc-research",
               "Three to ten keywords", "Provide three to ten keywords representing the article."),
        policy("title-page-identity", "identity", "title_page", "author_names_and_addresses_required", True, "bmc-research",
               "list the full names and institutional addresses for all authors", "The title page identifies authors and institutional addresses; identity details must come from the manuscript or user."),
        policy("declarations", "structure", "declarations", "required_section", True, "bmc-research",
               "All manuscripts must contain the following sections under the heading", "The research article includes the journal's Declarations subsections; statements require actual author, funding and ethics evidence."),
    ]
    frontiers = [
        policy("page-and-line-numbers", "layout", "document", "page_and_line_numbers_required", True, "frontiers-public-health",
               "must contain page and line numbers", "Page and line numbering facilitate manuscript review."),
        policy("abstract-citations", "citation", "abstract", "citations_allowed", False, "frontiers-public-health",
               "do not cite references, figures or tables", "The abstract excludes references, figures and tables."),
        policy("abstract-paragraph", "structure", "abstract", "maximum_paragraphs", 1, "frontiers-public-health",
               "abstract should be no longer than a single paragraph", "Keep the abstract to one paragraph while following the selected article type's required structure."),
        policy("table-native-format", "structure", "table", "editable_required", True, "frontiers-public-health",
               "Tables should be inserted at the end of the manuscript in an editable format", "Place editable tables at the end of the manuscript; retain table data and merge structure."),
        policy("table-caption-position", "layout", "table_caption", "placement", "immediately_before_table", "frontiers-public-health",
               "Table captions must be placed immediately before the table", "The table caption precedes its table and occupies one paragraph."),
        policy("figure-caption-position", "layout", "figure_caption", "placement", "end_of_manuscript", "frontiers-public-health",
               "Figure captions should be placed at the end of the manuscript", "Collect figure captions at the end of the manuscript."),
        policy("figure-resolution", "image", "image", "minimum_dpi", 300, "frontiers-public-health",
               "All images must have a resolution of 300 dpi at final size", "Check image resolution at its final physical size; resampling cannot create missing detail.", unit="dpi"),
        policy("editable-equations", "structure", "equation", "editable_required", True, "frontiers-public-health",
               "Equations should be inserted in editable format", "Keep native editable equations instead of rasterizing them."),
        policy("author-list", "identity", "title_page", "author_names_and_affiliations_required", True, "frontiers-public-health",
               "All names are listed together and separated by commas", "List exact author names and keyed affiliations. The source requires author identification, so this profile does not remove it."),
    ]
    return {
        "int-plos-one-research-word": {"name": "PLOS ONE research manuscript Word requirements", "aliases": ["PLOS ONE research", "PLOS ONE 投稿稿 Word"],
            "article_type": "Research article", "source_keys": ["plos-one"], "spacing": 2, "spacing_source": "plos-one",
            "spacing_anchor": "Manuscript text should be double-spaced", "columns": 1, "policies": one},
        "int-plos-comp-biol-research-word": {"name": "PLOS Computational Biology research manuscript Word requirements", "aliases": ["PLOS Computational Biology research", "PLOS Computational Biology 投稿稿 Word"],
            "article_type": "Research article", "source_keys": ["plos-comp-biol"], "spacing": 2, "spacing_source": "plos-comp-biol",
            "spacing_anchor": "Manuscript text should be double-spaced", "columns": 1, "policies": comp},
        "int-bmc-public-health-research-word": {"name": "BMC Public Health research article Word requirements", "aliases": ["BMC Public Health research", "BMC Public Health 研究论文 Word"],
            "article_type": "Research article", "source_keys": ["bmc-main", "bmc-research"], "spacing": 2, "spacing_source": "bmc-main",
            "spacing_anchor": "Use double-line spacing", "policies": bmc},
        "int-frontiers-public-health-word": {"name": "Frontiers in Public Health manuscript Word requirements", "aliases": ["Frontiers in Public Health Word", "Frontiers Public Health 投稿稿"],
            "article_type": "Manuscripts subject to the journal author guidelines", "source_keys": ["frontiers-public-health"], "spacing": 1,
            "spacing_source": "frontiers-public-health", "spacing_anchor": "The entire document should be single-spaced", "policies": frontiers},
    }


def _normalized(element):
    return " ".join(element.text_content().split())


def _fetch(item):
    key, url = item
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 ManuWeave official guideline verification"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data, status = response.read(), response.status
        content_type = response.headers.get("Content-Type", "")
    tree = html.fromstring(data, parser=html.HTMLParser(encoding="utf-8"))
    title = " ".join(tree.xpath("//title/text()"))
    if status != 200 or re.search(r"challenge|access denied|captcha", title, re.I):
        raise ValueError(f"Official guideline body unavailable: {key}")
    for node in tree.xpath("//script|//style|//nav|//footer"):
        node.drop_tree()
    return key, {"url": url, "title": title, "http_status": status, "content_type": content_type,
                 "sha256": hashlib.sha256(data).hexdigest(), "byte_count": len(data), "retrieved_at": DATE,
                 "source_verified": True, "submission_compliance_verified": False, "original_file_redistributed": False,
                 "file": f"official HTML response SHA-256 {hashlib.sha256(data).hexdigest()} (not redistributed)"}, tree


def _origin(tree, record, anchor):
    match = None
    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue
        if anchor.casefold() in _normalized(element).casefold():
            if match is None or len(_normalized(element)) < len(_normalized(match)):
                match = element
    if match is None:
        raise ValueError(f"Official source does not contain verified anchor {anchor!r}: {record['url']}")
    return {"url": record["url"], "file": record["file"],
            "locator": tree.getroottree().getpath(match) + "; normalized text anchor: " + anchor,
            "anchor": anchor, "response_sha256": record["sha256"], "retrieved_at": DATE}


def refresh():
    with ThreadPoolExecutor(max_workers=3) as executor:
        retrieved = list(executor.map(_fetch, URLS.items()))
    sources = {key: record for key, record, _ in retrieved}
    trees = {key: tree for key, _, tree in retrieved}
    documents = definitions()
    for identity, fact in documents.items():
        fact["sources"] = [sources[key] for key in fact["source_keys"]]
        fact["source_version"] = f"Official online author guidelines snapshot {DATE}; {fact['article_type']}"
        spacing_key = fact["spacing_source"]
        fact["spacing_origin"] = _origin(trees[spacing_key], sources[spacing_key], fact["spacing_anchor"])
        if "columns" in fact:
            fact["columns_origin"] = _origin(trees[spacing_key], sources[spacing_key], "Do not format text in multiple columns")
        for item in fact["policies"]:
            key = item["source_key"]
            item["source"] = _origin(trees[key], sources[key], item["anchor"])
        del fact["source_keys"]
    facts = {"retrieved_at": DATE, "source_policy": "Only paraphrased facts and response hashes are redistributed; no source pages or templates are bundled.",
             "documents": documents}
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "source-facts.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return facts


def build(facts):
    destination = HERE / "profiles"
    destination.mkdir(parents=True, exist_ok=True)
    for identity, fact in facts["documents"].items():
        rules = {role: {"line_spacing": fact["spacing"]} for role in ROLES}
        page = {"columns": fact["columns"]} if "columns" in fact else {}
        requirements = [{"id": f"{role}-line-spacing", "category": "typography", "target": role, "property": "line_spacing",
                         "expected": fact["spacing"], "unit": "ratio", "checking": "xml", "certainty": "verified", "applies_to": ["docx"],
                         "source": fact["spacing_origin"], "detail": "Apply the journal's explicit manuscript-wide line-spacing instruction."} for role in ROLES]
        if page:
            requirements.append({"id": "single-column", "category": "layout", "target": "page", "property": "columns", "expected": 1,
                                 "unit": "columns", "checking": "xml", "certainty": "verified", "applies_to": ["docx"],
                                 "source": fact["columns_origin"], "detail": "The journal explicitly prohibits a multi-column manuscript."})
        for item in fact["policies"]:
            requirements.append({key: value for key, value in item.items() if key not in {"source_key", "anchor"}} | {"applies_to": ["docx"]})
        profile = {"id": identity, "name": fact["name"], "version": "1.0.0", "aliases": fact["aliases"],
                   "scope": f"{fact['article_type']}; explicit Word spacing/layout and listed editorial requirements from the journal's own guide.",
                   "compliance": "source_backed_template_partial_coverage", "rules": rules, "page": page, "latex": {},
                   "sources": fact["sources"], "checks": [{"role": role, "property": "line_spacing", "expected": fact["spacing"]} for role in ROLES],
                   "template": {"family": "international-journals", "source_version": fact["source_version"],
                                "license": "rules_only_source_not_redistributed", "source_url": fact["sources"][0]["url"],
                                "assets": [], "engine_support": {"docx": "partial", "latex": "unsupported"}, "requirements": requirements,
                                "coverage_notes": ["This profile applies only the source-established spacing and layout properties; it preserves manuscript font and point-size choices.",
                                                   "The listed reference, figure, structure and identity policies require the corresponding host checks. Formatting does not invent facts or delete material.",
                                                   "A Word formatting pass does not establish complete journal submission compliance."]}}
        (destination / f"{identity}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch only the fixed official source pages and verify every anchor")
    arguments = parser.parse_args()
    data = refresh() if arguments.refresh else json.loads((HERE / "source-facts.json").read_text(encoding="utf-8"))
    build(data)
