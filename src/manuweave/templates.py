"""Source-linked declarative formatting rules; no original template files."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parent / "data" / "templates"
STYLE_EXTENSIONS = {".cls", ".sty", ".bst", ".rtx", ".clo", ".def", ".cfg", ".tex", ".ist"}
RESOURCE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".eps"}


class Origin(BaseModel):
    model_config = ConfigDict(extra="allow")
    url: str = Field(pattern=r"^https?://")
    file: str = Field(min_length=1)
    locator: str = Field(min_length=1)


class Requirement(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1)
    category: str
    target: str
    property: str
    expected: Any = None
    unit: str | None = None
    source: Origin
    certainty: Literal["verified", "conditional", "unknown"]
    checking: Literal["native_class", "xml", "host", "render"]
    applies_to: list[Literal["docx", "latex"]] = Field(min_length=1)
    detail: str = ""


class Asset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    destination: str | None = None


class Support(BaseModel):
    model_config = ConfigDict(extra="forbid")
    docx: Literal["native", "partial", "unsupported"]
    latex: Literal["native", "partial", "unsupported"]


class Template(BaseModel):
    model_config = ConfigDict(extra="allow")
    family: str = Field(min_length=1)
    source_version: str = Field(min_length=1)
    license: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https?://")
    assets: list[Asset] = Field(default_factory=list)
    engine_support: Support
    requirements: list[Requirement] = Field(min_length=1)
    coverage_notes: list[str] = Field(default_factory=list)
    fixture: str | None = None


def asset_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe template asset path")
    actual = ROOT.joinpath(*path.parts)
    if ROOT.resolve() not in actual.resolve().parents or actual.is_symlink():
        raise ValueError("Template asset escapes installed data")
    return actual


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _check_word_rule_evidence(profile, specification):
    """Only confirmed source rules may drive a journal's Word formatting."""
    if specification.engine_support.docx == "unsupported":
        return
    formats = list(profile.get("rules", {}).items())
    formats.append(("page", profile.get("page", {})))
    if profile.get("sections"):
        formats.append(("sections", profile["sections"]))
    formats.extend((profile.get("running") or {}).items())
    if profile.get("tables"):
        formats.append(("table", profile["tables"]))
    for target, properties in formats:
        for prop, expected in (properties or {}).items():
            if expected is None:
                continue
            supported = any(
                rule.target == target and rule.property == prop
                and rule.expected == expected and rule.certainty == "verified"
                and rule.checking == "xml" and "docx" in rule.applies_to
                for rule in specification.requirements
            )
            if not supported:
                raise ValueError(f"Unconfirmed journal formatting rule: {target}.{prop}")


def validate_template(profile):
    specification = Template.model_validate(profile["template"], strict=True)
    ids = [r.id for r in specification.requirements]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate template requirement IDs")
    _check_word_rule_evidence(profile, specification)
    if specification.assets or specification.fixture or any(profile["template"].get(key) for key in ("remote_archive", "remote_assets")):
        raise ValueError("Built-in formatting must contain JSON rules, not original template assets or downloads")
    return profile


def native_template(profile):
    """Formatting uses the local JSON-driven engines, never a bundled publisher class."""
    return False


def assets(profile):
    if "template" in profile:
        validate_template(profile)
    return []


def install_assets(profile, project):
    if "template" in profile:
        validate_template(profile)
    return []


def authenticated_asset(path):
    return False


def trusted_style_asset(path):
    return False


def guard_engine(profile, kind):
    if "template" not in profile:
        return
    validate_template(profile)
    support = profile["template"]["engine_support"][kind]
    if support == "unsupported":
        raise ValueError(f"{profile['id']} has no verified {kind} implementation; choose its supported native engine")


def materialize_fixture(profile, destination):
    """Generate an original synthetic article for testing the declared JSON rules."""
    validate_template(profile)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("Fixture destination must be new")
    destination.mkdir(parents=True)
    text = '\\documentclass{article}\n\\usepackage{amsmath}\n\\title{Synthetic formatting study}\n\\author{Fixture Author}\n\\begin{document}\n\\maketitle\n\\begin{abstract}\nThis synthetic summary describes document formatting without research claims.\n\\end{abstract}\n\\section{Introduction}\nA synthetic measurement is 12.5 and must remain unchanged.\n\\section{Methods}\n\\begin{equation}x=\\frac{1}{2}+\\alpha\\end{equation}\n\\begin{table}[ht]\\centering\n\\begin{tabular}{lr}Item&Value\\\\Fixture&12.5\\end{tabular}\n\\caption{Synthetic table}\\end{table}\n\\begin{figure}[ht]\\centering\\fbox{Synthetic graphic}\n\\caption{Synthetic figure}\\end{figure}\n\\begin{thebibliography}{9}\n\\bibitem{fixture} Fixture Author. Synthetic reference. 2026.\n\\end{thebibliography}\n\\end{document}\n'
    (destination / "main.tex").write_text(text, encoding="utf-8")
    return destination / "main.tex"


def _abstracts(text):
    results = re.findall(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.S)
    for match in re.finditer(r"\\abstract\s*(?:\[[^\]]*\]\s*)?\{", text):
        depth, position = 1, match.end()
        start = position
        while position < len(text) and depth:
            if text[position] == "\\" and position + 1 < len(text) and text[position + 1] in "{}%":
                position += 2
                continue
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
            position += 1
        if depth == 0:
            results.append(text[start:position - 1])
    return "\n".join(results)


def classify_native_diagnostic(root, main, issue):
    return issue


def _equal_format(actual, expected):
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_equal_format(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(_equal_format(actual[key], value) for key, value in expected.items())
    if isinstance(expected, bool) or isinstance(expected, str):
        return actual == expected
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)):
        return abs(actual - expected) < 0.06
    return actual == expected


def _role_matches(block, target, roles):
    role = (roles or {}).get(block["id"], block["role"])
    if role == "body_start":
        role = "body"
    if role == target:
        return True
    if target.endswith(("_zh", "_en")):
        base, language = target.rsplit("_", 1)
        if role != base:
            return False
        detected = "zh" if re.search(r"[\u3400-\u9fff]", block["text"]) else "en" if re.search(r"[A-Za-z]", block["text"]) else None
        return language == detected
    return role.endswith(("_zh", "_en")) and role[:-3] == target


def audit_requirements(source, profile, roles=None):
    """Audit extracted formatting values against the edited native document."""
    if "template" not in profile:
        return {"status": "NOT_APPLICABLE", "checks": [], "scope": "Authored layout"}
    validate_template(profile)
    source = Path(source)
    kind = "docx" if source.suffix.lower() == ".docx" else "latex"
    template = profile["template"]
    ir, latex_checks, abstract = None, [], ""
    if kind == "docx":
        from .word import inspect_docx
        ir = inspect_docx(source)
        abstract = "\n".join(block["text"] for block in ir["blocks"] if _role_matches(block, "abstract", roles))
    else:
        from .latex import inspect_applied_rules
        latex_checks = inspect_applied_rules(source, profile)["checks"]
        from .latex import _project, _read, _uncomment, _managed_layout, LAYOUT
        _, _, files = _project(source)
        abstract = _abstracts("\n".join(_uncomment(_read(path)) for path in files if path.suffix == ".tex" and not (path.name == LAYOUT and _managed_layout(path))))
    checks = []
    for rule in template["requirements"]:
        status, detail = "UNVERIFIED", "This extracted formatting condition requires a targeted check"
        if kind not in rule["applies_to"]:
            status, detail = "NOT_APPLICABLE", "Rule applies to the other document engine"
        elif rule["certainty"] == "unknown":
            status, detail = "UNKNOWN", "The source does not establish this value"
        elif rule["target"] == "abstract" and rule["property"] in {"citations_allowed", "abstract_citations_allowed", "reference_numbers_allowed"}:
            if not abstract.strip():
                status, detail = "UNKNOWN", "No abstract is available for this formatting check"
            elif rule["expected"] is False:
                command = bool(re.search(r"\\[A-Za-z]*cite[A-Za-z]*\*?\s*(?:\[[^\]]*\]\s*)*\{", abstract)) if kind == "latex" else False
                numeric = bool(re.search(r"[\[［]\s*\d+(?:\s*[-,，–]\s*\d+)*\s*[\]］]", abstract))
                author_year = bool(re.search(r"\([^)]*\b(?:19|20)\d{2}[a-z]?\)", abstract))
                found = numeric if rule["property"] == "reference_numbers_allowed" else command or numeric or author_year
                status = "FAIL" if found else "UNVERIFIED"
                detail = "Citation-like notation appears in the abstract" if found else "No explicit citation detected; arbitrary citation macros require review"
            else:
                status, detail = "NOT_APPLICABLE", "This format does not prohibit abstract citations"
        elif kind == "latex":
            matched = [check for check in latex_checks
                       if check["target"] == rule["target"] and check["property"] == rule["property"]
                       and _equal_format(check.get("expected"), rule["expected"])]
            if matched:
                status = "FAIL" if any(item["status"] == "FAIL" for item in matched) else "UNVERIFIED" if any(item["status"] in {"UNKNOWN", "UNVERIFIED"} for item in matched) else "PASS" if any(item["status"] == "PASS" for item in matched) else "NOT_APPLICABLE"
                detail = matched
        elif rule["checking"] == "xml":
            from .word import PROPERTIES, PAGE_PROPERTIES, audit_docx
            target, prop = rule["target"], rule["property"]
            expected = rule["expected"]
            source_expected = expected
            if prop == "alignment" and expected == "justify":
                expected = "both"
            if prop == "font_color" and isinstance(expected, str) and expected != "auto":
                expected = expected.upper()
            if prop == "size_pt" and isinstance(expected, (int, float)):
                expected = round(expected * 2) / 2
            if target == "page" and prop in PAGE_PROPERTIES:
                if prop == "mirror_margins":
                    from .word import _package, _xml, _val, NS
                    data = _package(source).get("word/settings.xml")
                    flag = _xml(data).find("w:mirrorMargins", NS) if data else None
                    observed = [flag is not None and _val(flag, default="1") not in {"0", "false", "off"}]
                else:
                    observed = [page.get(prop) for index, page in enumerate(ir["page"])
                                if prop not in profile.get("sections", {}).get("front_matter_page" if index == 0 else "body_page", {})
                                and not (index == 0 and profile.get("sections") and prop in {"columns", "column_widths_mm"})]
            elif target == "sections" and prop in profile.get("sections", {}):
                report = audit_docx(source, source, profile, roles)["style"]
                section_issues = [issue for issue in report["issues"] if "section" in issue or issue.get("property") in {"sections", "different_odd_even_headers"}]
                status = "FAIL" if section_issues else "PASS"
                detail = {"expected": expected, "section_check": status}
                observed = None
            elif prop in PROPERTIES:
                blocks = [block for block in ir["running"].get(target, []) if block["text"].strip()] if target in {"header", "footer"} else [block for block in ir["blocks"] if _role_matches(block, target, roles) and block["text"].strip()]
                observed = [block["format"].get(prop) for block in blocks]
            else:
                observed = None
            if observed is not None:
                status = "NOT_APPLICABLE" if not observed else "PASS" if all(_equal_format(value, expected) for value in observed) else "FAIL"
                detail = {"expected": source_expected, "observed": observed}
                if prop == "size_pt" and source_expected != expected:
                    detail.update(word_value=expected, exact_source_size=False, reason="OOXML represents font sizes in half-point units")
        checks.append({"id": rule["id"], "target": rule["target"], "property": rule["property"], "status": status, "detail": detail, "source": rule["source"]})
    statuses = [item["status"] for item in checks]
    status = "FAIL" if "FAIL" in statuses else "UNVERIFIED" if any(value in {"UNVERIFIED", "UNKNOWN"} for value in statuses) else "PASS"
    return {"status": status, "family": template["family"], "source_version": template["source_version"],
            "engine_support": template["engine_support"][kind], "checks": checks,
            "scope": "Extracted JSON formatting requirements"}
