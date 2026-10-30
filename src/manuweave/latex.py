"""Native, preservation-first LaTeX project adapter.

Compilation uses existing local TeX tools after strict static preflight, with
shell escape disabled and a temporary project copy. This is not an OS sandbox.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import tempfile
import time


MAX_FILES = 2000
MAX_BYTES = 128 * 1024 * 1024
LAYOUT = "manuweave-layout.tex"
INJECTION = "\\input{manuweave-layout.tex} % ManuWeave managed layout"
PREAMBLE = "manuweave-preamble.tex"
PRE_INJECTION = "\\input{manuweave-preamble.tex} % ManuWeave managed pre-class packages"
COMPILE_SETTINGS = "manuweave-compile.json"
CMSS_COMPAT = [
    r"{\fontencoding{T1}\fontfamily{cmss}\selectfont}",
    r"\DeclareFontShape{T1}{cmss}{b}{n}{<->ssub*cmss/bx/n}{}",
    r"\DeclareFontShape{T1}{cmss}{b}{it}{<->ssub*cmss/bx/it}{}",
    r"\DeclareFontShape{T1}{cmss}{b}{sl}{<->ssub*cmss/bx/sl}{}",
]
TEXT_EXTENSIONS = {".tex", ".sty", ".cls", ".bib", ".bst", ".cfg", ".def", ".rtx", ".clo", ".ltx"}
CLASS = re.compile(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^{}]+)\}")
DANGEROUS = re.compile(
    r"\\(?:write18|write|openout|openin|read|readline|directlua|latelua|luaexec|"
    r"catcode|csname|newread|newwrite|usepackage\s*(?:\[[^\]]*\])?\s*\{(?:shellesc|luacode|pythontex|minted))\b|\^\^",
    re.IGNORECASE,
)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _uncomment(text: str) -> str:
    return _comments(text, mask=False)


def _comments(text: str, mask: bool = True) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        for position, character in enumerate(line):
            if character != "%":
                continue
            cursor = position - 1
            while cursor >= 0 and line[cursor] == "\\":
                cursor -= 1
            if (position - cursor - 1) % 2 == 0:
                ending = "\n" if line.endswith("\n") else ""
                line = line[:position] + (" " * (len(line) - position - len(ending)) if mask else "") + ending
                break
        lines.append(line)
    return "".join(lines)


def _project(source: str | Path) -> tuple[Path, Path, list[Path]]:
    source = Path(source)
    if source.is_symlink():
        raise ValueError("Symlink project paths are not allowed")
    source = source.resolve()
    root = source if source.is_dir() else source.parent
    if not root.is_dir():
        raise ValueError("LaTeX project does not exist")
    if root.is_symlink() or source.is_symlink():
        raise ValueError("Symlink project paths are not allowed")
    files = []
    total = 0
    for item in root.rglob("*"):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise ValueError("Symlinks and junctions are not allowed in LaTeX projects")
        if root not in item.resolve().parents:
            raise ValueError("Project resource resolves outside its root")
        if item.is_file():
            if item.name in {".DS_Store"} or ".git" in item.relative_to(root).parts:
                continue
            total += item.stat().st_size
            files.append(item)
            if len(files) > MAX_FILES or total > MAX_BYTES:
                raise ValueError("LaTeX project exceeds file or byte limits")
    if source.is_file():
        if source.suffix.lower() != ".tex":
            raise ValueError("Expected a .tex main file or project directory")
        main = source
    else:
        candidates = [p for p in files if p.suffix == ".tex" and CLASS.search(_comments(_read(p)))]
        if len(candidates) != 1:
            raise ValueError("Specify the main .tex file when a project has zero or multiple document classes")
        main = candidates[0]
    if main not in files or not CLASS.search(_comments(_read(main))):
        raise ValueError("Main file has no documentclass declaration")
    return root, main, sorted(files)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _risks(root: Path, files: list[Path]) -> list[dict]:
    risks = []
    for path in files:
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        from .templates import trusted_style_asset
        if trusted_style_asset(path):
            continue
        text = _uncomment(_read(path))
        bad = DANGEROUS.search(text)
        if bad:
            risks.append({"file": path.relative_to(root).as_posix(), "reason": "unsafe_primitive", "token": bad.group(0)})
        if re.search(r"\\(?:input|include)\b(?!\s*\{)", text):
            risks.append({"file": path.relative_to(root).as_posix(), "reason": "unbraced_or_dynamic_input"})
        for match in re.finditer(r"\\(?:input|include|includegraphics|bibliography|addbibresource)\s*(?:\[[^\]]*\])?\s*\{([^{}]+)\}", text):
            for name in match.group(1).split(","):
                name = name.strip().replace("\\", "/")
                part = PurePosixPath(name)
                if (part.is_absolute() or ".." in part.parts or ":" in name
                        or any(c in name for c in "#$|~")):
                    risks.append({"file": path.relative_to(root).as_posix(), "reason": "unsafe_dependency_path", "path": name})
    return risks


def _semantic(path: Path) -> str:
    if path.suffix.lower() not in {".tex", ".sty", ".cls"}:
        return _hash(path.read_bytes())
    text = _read(path).replace(INJECTION + "\n", "").replace(PRE_INJECTION + "\n", "")
    text = text.replace(INJECTION, "").replace(PRE_INJECTION, "")
    text = CLASS.sub("", text)
    text = re.sub(r"\\bibliographystyle\s*\{[^{}]+\}", "", text)
    return _hash(re.sub(r"\s+", " ", _uncomment(text)).strip().encode())


def _managed_layout(path: Path) -> bool:
    if not path.is_file():
        return False
    lines = _read(path).splitlines()
    if len(lines) > 1 and lines[1].startswith("% ManuWeave declarative configuration: "):
        try:
            configuration = json.loads(lines[1].split(": ", 1)[1])
            return _read(path) == _render_layout(configuration)
        except (ValueError, TypeError, KeyError):
            return False
    return bool(lines and lines[0] == "% Generated by ManuWeave; layout only." and all(
        line in CMSS_COMPAT or re.fullmatch(r"\\(?:usepackage(?:\[[A-Za-z0-9_.,= +/\-]*\])?\{[A-Za-z0-9_\-]+\}|geometry\{[A-Za-z0-9_.,= +/\-]*\})", line)
        for line in lines[1:] if line.strip()))


def _managed_preamble(path: Path) -> bool:
    if not path.is_file():
        return False
    lines = _read(path).splitlines()
    metadata = set(_metadata_preamble({"rules": {role: {} for role in ("affiliation", "subtitle", "correspondence")}}))
    return bool(lines and lines[0] == "% Generated by ManuWeave; pre-class packages only." and all(
        line in metadata or re.fullmatch(r"\\RequirePackage(?:\[[A-Za-z0-9_.,= +/\-]*\])?\{[A-Za-z0-9_\-]+\}", line)
        for line in lines[1:] if line.strip()))


def _compile_settings(path):
    from .models import LaTeXRule
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(data) - {"format", "engine"} or data.get("format") != "manuweave-compile-v1":
        raise ValueError("Unrecognized native compilation settings")
    LaTeXRule.model_validate({k: v for k, v in data.items() if k != "format"}, strict=True)
    return data


def _managed_compile(path):
    try:
        return Path(path).stat().st_size < 4096 and bool(_compile_settings(path))
    except (OSError, ValueError, TypeError):
        return False


def inspect_latex(path: str | Path) -> dict:
    root, main, files = _project(path)
    blocks = []
    for file in files:
        if file.suffix != ".tex" or file.name in {LAYOUT, PREAMBLE}:
            continue
        from .templates import trusted_style_asset
        if trusted_style_asset(file):
            continue
        text = _read(file)
        for index, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("%"):
                continue
            role = "body"
            heading = re.search(r"\\(chapter|section|subsection|subsubsection)\*?\s*\{", line)
            if heading:
                role = {"chapter": "heading1", "section": "heading1", "subsection": "heading2", "subsubsection": "heading3"}[heading.group(1)]
            elif re.search(r"\\(?:begin\{(?:equation|align|gather)|\[)", line):
                role = "equation"
            elif "\\caption" in line:
                role = "caption"
            elif "\\begin{abstract}" in line:
                role = "abstract"
            blocks.append({"id": f"{file.relative_to(root).as_posix()}:{index}", "role": role,
                           "text": line, "source": {"file": file.relative_to(root).as_posix(), "line": index}})
    parser = "line_and_command_inventory"
    try:
        from pylatexenc.latexwalker import LatexWalker
        LatexWalker(_read(main)).get_latex_nodes(pos=0)
        parser = "pylatexenc+source_lines"
    except ImportError:
        pass
    return {"kind": "latex", "main": main.relative_to(root).as_posix(), "blocks": blocks,
            "inventory": {p.relative_to(root).as_posix(): {"sha256": _hash(p.read_bytes()), "content_sha256": _semantic(p)} for p in files if (p != root / LAYOUT or not _managed_layout(p)) and (p != root / PREAMBLE or not _managed_preamble(p)) and (p != root / COMPILE_SETTINGS or not _managed_compile(p))},
            "risks": _risks(root, files), "parser": parser}


def _preamble_commands(text: str):
    """Yield literal top-level declarations, never macro bodies or comments."""
    masked = _comments(text)
    marker = re.search(r"\\begin\s*\{document\}", masked)
    masked = masked[:marker.start()] if marker else masked
    declaration = re.compile(r"\\(documentclass|usepackage|RequirePackage|geometry|input|include)\s*(?:\[([^\]]*)\])?\s*\{([^{}]*)\}")
    depth = 0
    position = 0
    conditional_seen = False
    while position < len(masked):
        character = masked[position]
        if character == "\\":
            command = re.match(r"\\([A-Za-z@]+|.)", masked[position:])
            if not command:
                position += 1
                continue
            name = command.group(1)
            if name.startswith("if") and depth == 0:
                conditional_seen = True
            match = declaration.match(masked, position) if depth == 0 else None
            if match:
                yield match, conditional_seen
                position = match.end()
                continue
            if name in {"def", "gdef", "edef", "xdef"} and depth == 0:
                opening = masked.find("{", position + len(command.group(0)))
                if opening < 0:
                    return
                position = opening
                continue
            if name == "begin" and depth == 0:
                # Preamble environments can write literal TeX into files. Their
                # contents do not establish active global layout declarations.
                conditional_seen = True
            position += len(command.group(0))
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth = max(0, depth - 1)
        position += 1


def learn_latex_style(source: str | Path) -> dict:
    """Learn explicit native preamble layout without executing the template.

    Dynamic macros, conditionals, package-defined defaults and arbitrary style
    commands remain UNKNOWN. Source prose is never included in the profile.
    """
    root, main, files = _project(source)
    risks = _risks(root, files)
    if risks:
        raise ValueError(f"Unsafe LaTeX reference: {risks}")
    evidence: dict[str, dict] = {}
    unknown = []
    page = {}
    latex = {"packages": {}}
    visited = set()

    def record(key, value, path, position, text):
        location = {"file": path.relative_to(root).as_posix(), "line": text.count("\n", 0, position) + 1}
        prior = evidence.get(key)
        evidence[key] = {"value": value, "unit": "mm" if key.startswith("page.") and key != "page.columns" else None,
                         "status": "PASS", "confidence": 1.0, "source": location,
                         "condition": "literal, unconditional, top-level preamble declaration",
                         "exceptions": ([{"value": prior["value"], "source": prior["source"], "reason": "earlier explicit value overridden by later declaration"}] if prior and prior["value"] != value else [])}

    def dimensions(value):
        match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(mm|cm|in|pt)\s*", value)
        if not match:
            return None
        return float(match.group(1)) * {"mm": 1, "cm": 10, "in": 25.4, "pt": 25.4 / 72.27}[match.group(2)]

    def geometry(options, path, position, text):
        names = {"top": ["margin_top_mm"], "bottom": ["margin_bottom_mm"], "left": ["margin_left_mm"],
                 "right": ["margin_right_mm"], "margin": ["margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm"],
                 "hmargin": ["margin_left_mm", "margin_right_mm"], "vmargin": ["margin_top_mm", "margin_bottom_mm"],
                 "paperwidth": ["width_mm"], "paperheight": ["height_mm"]}
        for item in options.split(","):
            item = item.strip()
            papers = {"a4paper": (210, 297), "letterpaper": (215.9, 279.4), "a5paper": (148, 210), "legalpaper": (215.9, 355.6)}
            if item in papers:
                for key, value in zip(("width_mm", "height_mm"), papers[item]):
                    page[key] = value
                    record("page." + key, value, path, position, text)
                continue
            if "=" not in item:
                if item:
                    unknown.append({"status": "UNKNOWN", "property": "geometry." + item, "reason": "unsupported or nonnumeric geometry option"})
                continue
            key, raw = (part.strip() for part in item.split("=", 1))
            numeric = dimensions(raw)
            if key not in names or numeric is None:
                unknown.append({"status": "UNKNOWN", "property": "geometry." + key, "reason": "dynamic or unsupported dimension"})
                continue
            for target in names[key]:
                minimum, maximum = (50, 600) if target in {"width_mm", "height_mm"} else (5, 80)
                if not minimum <= numeric <= maximum:
                    unknown.append({"status": "UNKNOWN", "property": "page." + target, "reason": "explicit dimension lies outside the supported profile range"})
                    continue
                page[target] = round(numeric, 6)
                record("page." + target, page[target], path, position, text)

    def visit(path):
        if path in visited:
            unknown.append({"status": "UNKNOWN", "property": "preamble_input", "reason": "repeated or cyclic preamble input", "file": path.relative_to(root).as_posix()})
            return
        visited.add(path)
        text = _read(path)
        for match, conditional in _preamble_commands(text):
            name, options, content = match.group(1), match.group(2), match.group(3).strip()
            if conditional:
                unknown.append({"status": "UNKNOWN", "property": name, "reason": "declaration follows dynamic preamble control flow", "file": path.relative_to(root).as_posix()})
                continue
            if name in {"input", "include"}:
                dependency = path.parent / content
                if not dependency.suffix:
                    dependency = dependency.with_suffix(".tex")
                if dependency in files:
                    visit(dependency)
                else:
                    unknown.append({"status": "UNKNOWN", "property": "preamble_input", "reason": "input is not an available local source", "file": content})
                continue
            if name == "documentclass":
                try:
                    latex["documentclass"] = _token(content)
                    record("latex.documentclass", content, path, match.start(), text)
                    if (root / (content + ".cls")).is_file():
                        unknown.append({"status": "UNKNOWN", "property": "latex.documentclass", "reason": "custom class portability requires the original class file"})
                    literals = [_token(option.strip(), True) for option in (options or "").split(",") if option.strip()]
                    latex["options"] = literals
                    record("latex.options", literals, path, match.start(), text)
                    for option in literals:
                        if option in {"onecolumn", "twocolumn"}:
                            page["columns"] = 1 if option == "onecolumn" else 2
                            record("page.columns", page["columns"], path, match.start(), text)
                        elif option.endswith("paper"):
                            geometry(option, path, match.start(), text)
                except ValueError:
                    unknown.append({"status": "UNKNOWN", "property": "latex.options", "reason": "dynamic class or options"})
            elif name == "geometry":
                geometry(content, path, match.start(), text)
            elif name in {"usepackage", "RequirePackage"}:
                for package in content.split(","):
                    package = package.strip()
                    try:
                        _token(package)
                        if package == "geometry":
                            geometry(options or "", path, match.start(), text)
                            continue
                        package_options = _token(options or "", True)
                        latex["packages"][package] = package_options
                        record("latex.packages." + package, package_options, path, match.start(), text)
                        if (root / (package + ".sty")).is_file():
                            unknown.append({"status": "UNKNOWN", "property": "latex.packages." + package, "reason": "custom package portability requires the original style file"})
                    except ValueError:
                        unknown.append({"status": "UNKNOWN", "property": "latex.packages", "reason": "dynamic package declaration"})

    visit(main)
    if "columns" not in page:
        unknown.append({"status": "UNKNOWN", "property": "page.columns", "reason": "no explicit onecolumn or twocolumn option"})
    unknown.append({"status": "UNKNOWN", "property": "typography_and_custom_macros", "reason": "arbitrary class and package-defined typography is not inferred by this static learner"})
    fingerprint = _hash(main.read_bytes())
    return {"id": "learned-latex-" + fingerprint[:12], "name": "Learned explicit LaTeX preamble layout", "version": "1.0.0",
            "rules": {"body": {}}, "page": page, "latex": latex, "evidence": evidence,
            "sources": [{"file": main.relative_to(root).as_posix(), "sha256": fingerprint, "kind": "local_latex_reference"}],
            "scope": "Explicit static preamble declarations only; no source prose or template macro copying",
            "unknown": unknown, "heading_mapping": "chapter and section map to heading1; book/report hierarchy offsets require host role review"}


def _token(value: str, options: bool = False) -> str:
    pattern = r"[A-Za-z0-9_.,= +/\-]*" if options else r"[A-Za-z0-9_\-]+"
    if not re.fullmatch(pattern, str(value)):
        raise ValueError("Unsafe LaTeX profile token")
    return str(value)


FONT_FAMILIES = {
    "times": "ptm", "times roman": "ptm", "times/roman": "ptm",
    "nimbus roman": "ptm", "palatino": "ppl", "palladio": "ppl",
    "palatino/palladio": "ppl", "helvetica": "phv", "courier": "pcr",
    "computer modern roman": "cmr", "computer modern": "cmr",
    "computer modern sans serif": "cmss", "computer modern sans": "cmss",
    "computer modern typewriter": "cmtt", "latin modern roman": "lmr",
    "latin modern sans": "lmss", "latin modern sans serif": "lmss",
    "tex gyre termes": "qtm", "tex gyre pagella": "qpl", "tex gyre heros": "qhv",
}
FONT_SELECTORS = {
    "linux libertine": (r"\ifPDFTeX\fontencoding{T1}\fi\libertine", "libertine", ""),
    "linux libertine o": (r"\ifPDFTeX\fontencoding{T1}\fi\libertine", "libertine", ""),
    "linux biolinum": (r"\ifPDFTeX\fontencoding{T1}\fi\biolinum", "libertine", ""),
    "linux biolinum o": (r"\ifPDFTeX\fontencoding{T1}\fi\biolinum", "libertine", ""),
    "stix two text": (r"\fontencoding{T1}\fontfamily{stix2}\selectfont", "stix2", "nomath,notextcomp"),
    "stixgeneral": (r"\fontencoding{T1}\fontfamily{stix}\selectfont", "stix", "nomath,notextcomp"),
    "newtxtext": (r"\fontfamily{ntxtlf}\selectfont", "newtxtext", ""),
}
LAYOUT_FORMAT = "manuweave-declarative-layout-v1"
LAYOUT_COMMENT = "% ManuWeave declarative configuration: "


def _custom_carriers(text):
    text = _uncomment(text)
    commands = {"titleblock": "@?maketitle", "caption": "caption", "heading1": "section",
                "heading2": "subsection", "heading3": "subsubsection", "heading4": "paragraph", "heading5": "subparagraph"}
    blocked = [role for role, name in commands.items()
               if re.search(r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{?\\(?:" + name + r")\b|\\def\s*\\(?:" + name + r")\b", text)]
    if re.search(r"\\(?:newenvironment|renewenvironment)\*?\s*\{abstract\}", text):
        blocked.append("abstract")
    return sorted(blocked)


def _metadata_preamble(profile, carrier_text=""):
    lines = []
    for role in ("affiliation", "subtitle", "correspondence"):
        if role in profile.get("rules", {}):
            lines.extend([r"\makeatletter", "\\providecommand{\\mw" + role + "}{}"])
            if not re.search(r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{?\\" + role + r"\b|\\def\s*\\" + role + r"\b", _uncomment(carrier_text)):
                lines.append("\\providecommand{\\" + role + "}[1]{\\g@addto@macro\\mw" + role + "{{#1}\\par}}")
            lines.append(r"\makeatother")
    return lines


def _preamble(profile, carrier_text=""):
    lines = ["% Generated by ManuWeave; pre-class packages only."]
    for package, package_options in sorted(profile.get("latex", {}).get("pre_class_packages", {}).items()):
        package = _token(package)
        if package.lower() in {"shellesc", "pythontex", "minted", "luacode"}:
            raise ValueError("Unsafe pre-class package")
        package_options = _token(str(package_options), True)
        lines.append("\\RequirePackage" + ("[" + package_options + "]" if package_options else "") + "{" + package + "}")
    lines.extend(_metadata_preamble(profile, carrier_text))
    return lines


def _dimension(value, unit="bp"):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not -1000 <= value <= 1000:
        raise ValueError("Invalid declarative layout dimension")
    return f"{value:.9g}{unit}"


def _font_name(value):
    if not isinstance(value, str) or len(value) > 200 or not re.fullmatch(r"[\w .,+/\-]+", value):
        raise ValueError("Unsafe declarative font name")
    return value


def _format_tex(properties, font_commands):
    """Produce format-only commands from the typed paragraph-rule whitelist."""
    commands = []
    font = properties.get("font")
    if font:
        family = FONT_FAMILIES.get(font.casefold())
        selector = FONT_SELECTORS.get(font.casefold())
        commands.append("\\fontfamily{" + family + "}\\selectfont" if family else selector[0] if selector else font_commands[font])
    if properties.get("east_asia_font"):
        commands.append("\\CJKfontspec{" + _font_name(properties["east_asia_font"]) + "}")
    if "size_pt" in properties:
        baseline = _dimension(properties["line_spacing_pt"]) if "line_spacing_pt" in properties else r"\baselineskip"
        commands.append("\\fontsize{" + _dimension(properties["size_pt"]) + "}{" + baseline + "}\\selectfont")
    elif "line_spacing_pt" in properties:
        commands.append("\\setlength{\\baselineskip}{" + _dimension(properties["line_spacing_pt"]) + "}")
    if "line_spacing" in properties:
        commands.append("\\setstretch{" + f"{properties['line_spacing']:.9g}" + "}")
    for property_name, yes, no in (("bold", r"\bfseries", r"\mdseries"), ("italic", r"\itshape", r"\upshape")):
        if property_name in properties:
            commands.append(yes if properties[property_name] else no)
    if properties.get("font_color") not in {None, "auto"}:
        commands.append("\\color[HTML]{" + properties["font_color"].upper() + "}")
    alignment = properties.get("alignment")
    if alignment:
        commands.append({"left": r"\RaggedRight", "right": r"\RaggedLeft", "center": r"\centering",
                         "justify": r"\justifying", "both": r"\justifying"}[alignment])
    for key, length in (("first_line_pt", "parindent"), ("left_indent_pt", "leftskip"), ("right_indent_pt", "rightskip")):
        if key in properties:
            commands.append("\\setlength{\\" + length + "}{" + _dimension(properties[key]) + "}")
    return "".join(commands)


def _block_tex(properties, content, font_commands):
    before = "\\vspace*{" + _dimension(properties["space_before_pt"]) + "}" if "space_before_pt" in properties else ""
    after = "\\vspace{" + _dimension(properties["space_after_pt"]) + "}" if "space_after_pt" in properties else ""
    return before + "\\begingroup\\mwbodyparagraphfalse" + _format_tex(properties, font_commands) + " " + content + "\\par\\endgroup" + after


def _render_layout(specification):
    """Render our own controlled layout, never a publisher template program."""
    from .models import FormatRule, PageRule, RunningRule
    allowed = {"format", "page", "rules", "running", "packages", "compatibility", "keywords_mode", "blocked_carriers"}
    if not isinstance(specification, dict) or set(specification) != allowed or specification["format"] != LAYOUT_FORMAT:
        raise ValueError("Unrecognized declarative layout configuration")
    page = PageRule.model_validate(specification["page"], strict=True).model_dump(exclude_none=True)
    rules = {role: FormatRule.model_validate(rule, strict=True).model_dump(exclude_none=True)
             for role, rule in specification["rules"].items()}
    from .models import RoleMap
    RoleMap.model_validate({"roles": {role: role for role in rules}}, strict=True)
    running = RunningRule.model_validate(specification["running"], strict=True).model_dump(exclude_none=True)
    if specification["keywords_mode"] not in {"command", "environment"}:
        raise ValueError("Unknown keywords carrier")
    if specification["compatibility"] not in ([], ["cmss_bold_alias"]):
        raise ValueError("Unknown native compatibility operation")
    blocked = specification["blocked_carriers"]
    if not isinstance(blocked, list) or any(role not in {"titleblock", "caption", "abstract", "heading1", "heading2", "heading3", "heading4", "heading5"} for role in blocked):
        raise ValueError("Unknown custom carrier")
    lines = ["% Generated by ManuWeave; layout only.",
             LAYOUT_COMMENT + json.dumps(specification, ensure_ascii=True, sort_keys=True, separators=(",", ":"))]
    packages = {}
    for item in specification["packages"]:
        if not isinstance(item, dict) or set(item) != {"name", "options"}:
            raise ValueError("Invalid declarative package")
        name, options = _token(item["name"]), _token(item["options"], True)
        if name.lower() in {"shellesc", "pythontex", "minted", "luacode"}:
            raise ValueError("Unsafe package requested")
        packages[name] = options

    def require(name, options=""):
        if name in packages and options and packages[name] not in {"", options}:
            raise ValueError(f"Template package option conflict: {name}")
        packages.setdefault(name, options)

    all_rules = [*rules.values(), *running.values()]
    fonts = sorted({_font_name(rule["font"]) for rule in all_rules if rule.get("font") and rule["font"].casefold() not in FONT_FAMILIES and rule["font"].casefold() not in FONT_SELECTORS})
    for rule in all_rules:
        selector = FONT_SELECTORS.get(rule.get("font", "").casefold())
        if selector:
            require(selector[1], selector[2])
            require("iftex")
    cjk = any(rule.get("east_asia_font") for rule in all_rules)
    font_commands = {font: "\\mwfont" + chr(65 + index) for index, font in enumerate(fonts)}
    if len(fonts) > 26:
        raise ValueError("Too many distinct role fonts")
    if fonts or cjk:
        require("fontspec")
    if cjk:
        require("xeCJK")
    if rules or running:
        require("etoolbox")
        require("ragged2e")
    if any("line_spacing" in rule for rule in all_rules):
        require("setspace")
    if any("size_pt" in rule for rule in all_rules):
        # Physical bp values need scalable CM text/math at fractional TeX pt.
        require("fix-cm")
    if any(rule.get("font_color") not in {None, "auto"} for rule in all_rules):
        require("xcolor")
    if page:
        require("geometry")
    if any(re.fullmatch(r"heading[1-6]", role) and role not in blocked for role in rules):
        require("titlesec")
    if "caption" not in blocked and any(role in rules for role in ("caption", "figure_caption", "table_caption")):
        require("caption")
    restore_fonts = bool(fonts or cjk or any(rule.get("font", "").casefold() in FONT_SELECTORS for rule in all_rules))
    if restore_fonts:
        lines.extend([r"\makeatletter", r"\let\mworiginalrmdefault\rmdefault", r"\let\mworiginalsfdefault\sfdefault",
                      r"\let\mworiginalttdefault\ttdefault", r"\let\mworiginalfamilydefault\familydefault",
                      r"\let\mworiginalencodingdefault\encodingdefault", r"\edef\mworiginalencoding{\f@encoding}",
                      r"\edef\mworiginalfamily{\f@family}", r"\edef\mworiginalseries{\f@series}",
                      r"\edef\mworiginalshape{\f@shape}", r"\makeatother"])
    for name, options in sorted(packages.items()):
        # No-option duplicate loading is harmless for packages loaded by the source.
        lines.append("\\usepackage" + ("[" + options + "]" if options else "") + "{" + name + "}")
    for font, command in font_commands.items():
        lines.append("\\newfontfamily" + command + "{" + font + "}")
    if restore_fonts:
        lines.extend([r"\let\rmdefault\mworiginalrmdefault", r"\let\sfdefault\mworiginalsfdefault",
                      r"\let\ttdefault\mworiginalttdefault", r"\let\familydefault\mworiginalfamilydefault",
                      r"\let\encodingdefault\mworiginalencodingdefault",
                      r"\fontencoding{\mworiginalencoding}\fontfamily{\mworiginalfamily}\fontseries{\mworiginalseries}\fontshape{\mworiginalshape}\selectfont"])
    if any("size_pt" in rule for rule in all_rules):
        # The base CM extension family otherwise only declares discrete sizes.
        lines.append(r"\DeclareFontShape{OMX}{cmex}{m}{n}{<-7.5>cmex7<7.5-8.5>cmex8<8.5-9.5>cmex9<9.5->cmex10}{}")
    lines.append(r"\newif\ifmwbodyparagraph")
    lines.append(r"\newif\ifmwtablebodyfont")
    lines.append(r"\AtBeginDocument{\mwbodyparagraphtrue}")
    lines.append(r"\AtBeginDocument{\mwtablebodyfonttrue}")
    if rules:
        for environment in ("figure", "figure*", "table", "table*", "tabular", "tabular*"):
            lines.append("\\AtBeginEnvironment{" + environment + r"}{\mwbodyparagraphfalse}")
    geometry = []
    mirrored = page.get("mirror_margins") is True
    for key, option in (("margin_top_mm", "top"), ("margin_bottom_mm", "bottom"),
                        ("margin_left_mm", "inner" if mirrored else "left"), ("margin_right_mm", "outer" if mirrored else "right"),
                        ("width_mm", "paperwidth"), ("height_mm", "paperheight")):
        if key in page:
            geometry.append(option + "=" + _dimension(page[key], "mm"))
    if mirrored:
        geometry.append("twoside")
    elif page.get("mirror_margins") is False:
        geometry.append("oneside")
    if geometry:
        lines.append("\\geometry{" + ",".join(geometry) + "}")
    if "column_gap_mm" in page:
        lines.append("\\setlength{\\columnsep}{" + _dimension(page["column_gap_mm"], "mm") + "}")
    if "footer_distance_mm" in page and "margin_bottom_mm" in page:
        lines.append("\\setlength{\\footskip}{\\dimexpr " + _dimension(page["margin_bottom_mm"] - page["footer_distance_mm"], "mm") + "\\relax}")
    if "header_distance_mm" in page and "margin_top_mm" in page:
        lines.append("\\setlength{\\headsep}{\\dimexpr " + _dimension(page["margin_top_mm"] - page["header_distance_mm"], "mm") + "-\\headheight\\relax}")

    body = rules.get("body", {})
    if body:
        commands = _format_tex(body, font_commands)
        if "space_after_pt" in body:
            commands += "\\setlength{\\parskip}{" + _dimension(body["space_after_pt"]) + "}"
        lines.append("\\AtBeginDocument{" + commands + "}")
        if body.get("space_before_pt"):
            lines.append("\\AddToHook{para/before}{\\ifmwbodyparagraph\\vspace{" + _dimension(body["space_before_pt"]) + "}\\fi}")
    heading_commands = {"heading1": "section", "heading2": "subsection", "heading3": "subsubsection",
                        "heading4": "paragraph", "heading5": "subparagraph"}
    for role, command in heading_commands.items():
        if role not in rules or role in blocked:
            continue
        rule = rules[role]
        font_rule = {key: value for key, value in rule.items() if key not in {"left_indent_pt", "first_line_pt"}}
        lines.append("\\titleformat{\\" + command + "}{\\mwbodyparagraphfalse" + _format_tex(font_rule, font_commands) + "}{\\the" + command + "}{1em}{}")
        if any(key in rule for key in ("space_before_pt", "space_after_pt", "left_indent_pt")):
            lines.append("\\titlespacing*{\\" + command + "}{" + _dimension(rule.get("left_indent_pt", 0)) + "}{" + _dimension(rule.get("space_before_pt", 0)) + "}{" + _dimension(rule.get("space_after_pt", 0)) + "}")
    if "abstract" in rules and "abstract" not in blocked:
        rule = rules["abstract"]
        inner = {key: value for key, value in rule.items() if key not in {"left_indent_pt", "right_indent_pt"}}
        margins = "".join("\\setlength{\\" + length + "}{" + _dimension(rule[key]) + "}"
                          for key, length in (("left_indent_pt", "leftmargin"), ("right_indent_pt", "rightmargin")) if key in rule)
        if "first_line_pt" in rule:
            margins += "\\setlength{\\listparindent}{" + _dimension(rule["first_line_pt"]) + "}\\setlength{\\itemindent}{" + _dimension(rule["first_line_pt"]) + "}"
        before = "\\vspace{" + _dimension(rule["space_before_pt"]) + "}" if "space_before_pt" in rule else ""
        after = "\\vspace{" + _dimension(rule["space_after_pt"]) + "}" if "space_after_pt" in rule else ""
        heading = _block_tex(rules.get("abstract_heading", {"alignment": "center", "bold": True}), r"\abstractname", font_commands)
        lines.append("\\renewenvironment{abstract}{\\par\\mwbodyparagraphfalse" + before + heading + "\\begin{list}{}{" + margins + "}\\item[]" + _format_tex(inner, font_commands) + "}{\\par\\end{list}" + after + "}")
    for environment, role in (("equation", "equation"), ("equation*", "equation"),
                              ("align", "equation"), ("align*", "equation"), ("displaymath", "equation"),
                              ("thebibliography", "reference"), ("tabular", "table_body"), ("tabular*", "table_body"),
                              ("table", "table")):
        if role not in rules:
            continue
        rule = rules[role]
        omitted = {"alignment", "first_line_pt", "left_indent_pt", "right_indent_pt"} if role == "equation" else {"first_line_pt", "left_indent_pt", "right_indent_pt"} if role == "reference" else set()
        commands = _format_tex({key: value for key, value in rule.items() if key not in omitted}, font_commands)
        if role == "equation":
            for key, lengths in (("space_before_pt", ("abovedisplayskip", "abovedisplayshortskip")),
                                 ("space_after_pt", ("belowdisplayskip", "belowdisplayshortskip"))):
                if key in rule:
                    commands += "".join("\\setlength{\\" + length + "}{" + _dimension(rule[key]) + "}" for length in lengths)
        if environment == "thebibliography":
            lines.append("\\apptocmd{\\thebibliography}{\\mwbodyparagraphfalse" + commands + "}{}{\\PackageError{manuweave}{Cannot apply reference format}{The bibliography carrier is not supported}}")
        elif environment in {"tabular", "tabular*"}:
            lines.append("\\AtBeginEnvironment{" + environment + "}{\\ifmwtablebodyfont\\mwbodyparagraphfalse" + commands + "\\fi}")
        else:
            lines.append("\\AtBeginEnvironment{" + environment + "}{\\mwbodyparagraphfalse" + commands + "}")
    if "abstract_heading" in rules and "abstract" not in rules and "abstract" not in blocked:
        lines.extend([r"\let\mwabstractname\abstractname",
                      "\\renewcommand{\\abstractname}{{" + _format_tex(rules["abstract_heading"], font_commands) + r"\mwabstractname}}"])
    if "keywords" in rules:
        rule = rules["keywords"]
        if specification["keywords_mode"] == "command":
            lines.append("\\providecommand{\\keywords}[1]{" + _block_tex(rule, "#1", font_commands) + "}")
        else:
            before = "\\vspace{" + _dimension(rule["space_before_pt"]) + "}" if "space_before_pt" in rule else ""
            after = "\\vspace{" + _dimension(rule["space_after_pt"]) + "}" if "space_after_pt" in rule else ""
            lines.append("\\providecommand{\\keywords}{\\par" + before + "\\begingroup\\mwbodyparagraphfalse" + _format_tex(rule, font_commands) + "}")
            lines.append("\\providecommand{\\endkeywords}{\\par\\endgroup" + after + "}")
    if "titleblock" not in blocked and any(role in rules for role in ("title", "author", "affiliation", "subtitle", "correspondence")):
        lines.append(r"\makeatletter")
        for role in ("affiliation", "subtitle", "correspondence"):
            lines.append("\\providecommand{\\mw" + role + "}{}")
        title = _block_tex(rules.get("title", {}), r"\@title", font_commands)
        author_rule = rules.get("author", {})
        author = _block_tex(author_rule, r"\begin{tabular}[t]{c}\@author\end{tabular}", font_commands)
        chunks = [title]
        if "subtitle" in rules:
            chunks.append(_block_tex(rules["subtitle"], r"\mwsubtitle", font_commands))
        chunks.append(author)
        for role in ("affiliation", "correspondence"):
            if role in rules:
                chunks.append(_block_tex(rules[role], "\\mw" + role, font_commands))
        chunks.append(r"\ifx\@date\@empty\else\begingroup\@date\par\endgroup\fi")
        lines.append("\\renewcommand{\\@maketitle}{\\begingroup\\mwtablebodyfontfalse\\let\\footnote\\thanks " + "".join(chunks) + "\\endgroup}")
        lines.append(r"\makeatother")
    if "caption" not in blocked and any(role in rules for role in ("caption", "figure_caption", "table_caption")):
        base_font = r"\mwbodyparagraphfalse\setlength{\leftskip}{0bp}\setlength{\rightskip}{0bp}\setlength{\parindent}{0bp}\setlength{\parskip}{0bp}"
        lines.append("\\DeclareCaptionFont{mwcaptionbase}{" + base_font + "}")
        lines.append(r"\captionsetup{font+=mwcaptionbase}")
        for kind, role in (("figure", "figure_caption"), ("table", "table_caption")):
            rule = rules.get(role, rules.get("caption"))
            if rule is None:
                continue
            macro = "mw" + kind + "caption"
            font_rule = {key: value for key, value in rule.items() if key not in {"left_indent_pt", "right_indent_pt", "first_line_pt"}}
            lines.append("\\DeclareCaptionFont{" + macro + "}{" + base_font + _format_tex(font_rule, font_commands) + "}")
            settings = ["font=" + macro, "singlelinecheck=false"]
            if "left_indent_pt" in rule or "right_indent_pt" in rule:
                settings.append("margin={" + _dimension(rule.get("left_indent_pt", 0)) + "," + _dimension(rule.get("right_indent_pt", 0)) + "}")
            if "space_before_pt" in rule:
                settings.append("aboveskip=" + _dimension(rule["space_before_pt"]))
            if "space_after_pt" in rule:
                settings.append("belowskip=" + _dimension(rule["space_after_pt"]))
            if rule.get("alignment"):
                settings.append("justification=" + {"center": "centering", "left": "raggedright", "right": "raggedleft", "justify": "justified", "both": "justified"}[rule["alignment"]])
            lines.append("\\captionsetup[" + kind + "]{" + ",".join(settings) + "}")
    if running:
        lines.append(r"\makeatletter")
        for role, carriers in (("header", ("@oddhead", "@evenhead")), ("footer", ("@oddfoot", "@evenfoot"))):
            if role in running:
                for carrier in carriers:
                    lines.append("\\AtBeginDocument{\\pretocmd{\\" + carrier + "}{" + _format_tex(running[role], font_commands) + "}{}{}}")
        lines.append(r"\makeatother")
    if "cmss_bold_alias" in specification["compatibility"]:
        lines.extend(CMSS_COMPAT)
    return "\n".join(lines) + "\n"


def _layout(profile: dict, original: str, carrier_text: str | None = None) -> str:
    from .models import FormatRule, PageRule, RunningRule
    from .templates import native_template
    original = _uncomment(original)
    carrier_text = _uncomment(carrier_text if carrier_text is not None else original)
    page = {} if native_template(profile) else PageRule.model_validate(profile.get("page", {}), strict=True).model_dump(exclude_none=True)
    rules = {role: FormatRule.model_validate(rule, strict=True).model_dump(exclude_none=True)
             for role, rule in profile.get("rules", {}).items()}
    # A language-specific rule is selected only for an identifiable carrier.
    for role, pattern in (("title", r"\\title\s*\{(.*?)\}"),
                          ("abstract", r"\\begin\{abstract\}(.*?)\\end\{abstract\}"),
                          ("keywords", r"\\keywords\s*\{(.*?)\}")):
        matches = re.findall(pattern, carrier_text, re.S)
        languages = {"zh" if re.search(r"[\u3400-\u9fff]", match) else "en" for match in matches}
        if len(languages) == 1:
            language = next(iter(languages))
            if role + "_" + language in rules:
                rules[role] = rules[role + "_" + language]
    declarations = [match for match, conditional in _preamble_commands(original)
                    if not conditional and match.group(1) in {"usepackage", "RequirePackage"}]
    packages = []
    for name, options in sorted(profile.get("latex", {}).get("packages", {}).items()):
        name = _token(name)
        options = _token(",".join(options) if isinstance(options, list) else str(options or ""), True)
        existing = next((match for match in declarations if name in [item.strip() for item in match.group(3).split(",")]), None)
        if existing:
            if options and set(options.split(",")) != set((existing.group(2) or "").split(",")):
                raise ValueError(f"Template package option conflict: {name}")
            # The generator can safely repeat an option-free load.
            options = ""
        packages.append({"name": name, "options": options})
    running = RunningRule.model_validate(profile.get("running") or {}, strict=True).model_dump(exclude_none=True)
    specification = {"format": LAYOUT_FORMAT, "page": page, "rules": rules, "running": running,
                     "packages": packages, "compatibility": profile.get("latex", {}).get("compatibility", []),
                     "keywords_mode": "environment" if re.search(r"\\begin\{keywords\}", carrier_text) else "command",
                     "blocked_carriers": _custom_carriers(carrier_text)}
    return _render_layout(specification)


def _carrier_text(files):
    return "\n".join(_read(path) for path in files if path.suffix == ".tex" and path.name not in {LAYOUT, PREAMBLE})


def inspect_applied_rules(source: str | Path, profile: dict) -> dict:
    """Check generated rule application and real standard-document carriers.

    These are structural checks of the emitted controls. Actual glyph metrics,
    overflow and renderer font substitution still require PDF inspection.
    """
    root, main, files = _project(source)
    text = _uncomment(_carrier_text(files))
    custom = _custom_carriers(text)
    try:
        expected = _layout(profile, _read(main), text)
        exact = (root / LAYOUT).is_file() and _read(root / LAYOUT) == expected
    except (ValueError, TypeError, KeyError):
        exact = False
    carriers = {
        "body": bool(re.search(r"\\begin\{document\}", text)),
        "title": bool(re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{", text) and r"\maketitle" in text),
        "author": bool(re.search(r"\\author\s*(?:\[[^\]]*\])?\s*\{", text) and r"\maketitle" in text),
        "abstract": r"\begin{abstract}" in text,
        "abstract_heading": r"\begin{abstract}" in text,
        "keywords": bool(re.search(r"\\keywords\s*\{|\\begin\{keywords\}", text)),
        "reference": bool(re.search(r"\\begin\{thebibliography\}|\\bibliography\s*\{", text)),
        "references_heading": bool(re.search(r"\\begin\{thebibliography\}|\\bibliography\s*\{", text)),
        "equation": bool(re.search(r"\\begin\{(?:equation\*?|align\*?|displaymath)\}", text)),
        "table": r"\begin{table}" in text,
        "table_body": bool(re.search(r"\\begin\{tabular\*?\}", text)),
        "figure_caption": bool(re.search(r"\\begin\{figure\*?\}.*?\\caption\b", text, re.S)),
        "table_caption": bool(re.search(r"\\begin\{table\*?\}.*?\\caption\b", text, re.S)),
        "caption": r"\caption" in text,
    }
    for role in ("affiliation", "subtitle", "correspondence"):
        carriers[role] = bool(re.search(r"\\" + role + r"\s*\{", text) and r"\maketitle" in text)
    for index, command in enumerate(("section", "subsection", "subsubsection", "paragraph", "subparagraph"), 1):
        carriers["heading" + str(index)] = bool(re.search(r"\\" + command + r"\*?\s*(?:\[[^\]]*\])?\s*\{", text))
    supported_roles = set(carriers) - {"references_heading"}
    supported_properties = {"font", "east_asia_font", "size_pt", "bold", "italic", "font_color", "alignment",
                            "line_spacing", "line_spacing_rule", "line_spacing_pt", "first_line_pt",
                            "left_indent_pt", "right_indent_pt", "space_before_pt", "space_after_pt"}
    checks = []
    for role, properties in profile.get("rules", {}).items():
        base = role[:-3] if role.endswith(("_zh", "_en")) else role
        present = carriers.get(base, False)
        alias = base in {"title", "abstract", "keywords"} and role != base
        language_matches = []
        languages = set()
        if base in {"title", "abstract", "keywords"}:
            pattern = {"title": r"\\title\s*\{(.*?)\}", "abstract": r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
                       "keywords": r"\\keywords\s*\{(.*?)\}"}[base]
            language_matches = re.findall(pattern, text, re.S)
            languages = {"zh" if re.search(r"[\u3400-\u9fff]", value) else "en" for value in language_matches}
        if alias:
            present = role[-2:] in languages
        for key, value in properties.items():
            status, reason = "PASS", None
            if not exact:
                status, reason = "FAIL", "generated_layout_mismatch"
            elif not present:
                unusual = (base == "affiliation" and r"\affil" in text) or (base == "equation" and (r"\[" in text or "$$" in text))
                status, reason = ("UNVERIFIED", "nonstandard_carrier") if unusual else ("NOT_APPLICABLE", "carrier_absent")
            elif base not in supported_roles or key not in supported_properties:
                status, reason = "UNVERIFIED", "property_not_implemented"
            elif alias and len(languages) > 1:
                status, reason = "UNVERIFIED", "mixed_language_carriers_need_individual_role_mapping"
            elif role == base and len(languages) == 1 and base + "_" + next(iter(languages)) in profile.get("rules", {}):
                status, reason = "NOT_APPLICABLE", "language_specific_rule_selected"
            elif (base in {"title", "author", "affiliation", "subtitle", "correspondence"} and "titleblock" in custom
                  or base in {"abstract", "abstract_heading"} and "abstract" in custom
                  or base in {"caption", "figure_caption", "table_caption"} and "caption" in custom
                  or base in custom):
                status, reason = "UNVERIFIED", "source_defines_custom_title_carrier" if "titleblock" in custom else "source_defines_custom_format_carrier"
            elif role != base and not alias:
                status, reason = "UNVERIFIED", "language_specific_carrier_not_implemented"
            elif base == "equation" and key in {"alignment", "first_line_pt", "left_indent_pt", "right_indent_pt"}:
                status, reason = "UNVERIFIED", "math_position_requires_equation_specific_rule"
            elif re.fullmatch(r"heading[1-6]", base) and key == "first_line_pt":
                status, reason = "UNVERIFIED", "heading_label_hanging_requires_structural_rule"
            elif base in {"caption", "figure_caption", "table_caption"} and key == "first_line_pt":
                status, reason = "UNVERIFIED", "caption_hanging_requires_label_specific_rule"
            elif base == "abstract_heading" and "abstract" not in profile.get("rules", {}) and key in {"alignment", "first_line_pt", "left_indent_pt", "right_indent_pt", "space_before_pt", "space_after_pt"}:
                status, reason = "UNVERIFIED", "abstract_label_paragraph_requires_full_abstract_carrier"
            elif base in {"table_body", "table", "reference"} and key in {"space_before_pt", "space_after_pt", "first_line_pt", "left_indent_pt", "right_indent_pt"}:
                status, reason = "UNVERIFIED", "list_or_table_spacing_requires_structural_rule"
            elif base in {"title", "author", "affiliation", "subtitle", "correspondence"} and re.search(r"\\(?:newcommand|renewcommand|providecommand)\s*\{?\\(?:@?maketitle|" + re.escape(base) + r")\b|\\def\s*\\@?maketitle", text):
                status, reason = "UNVERIFIED", "source_defines_custom_title_carrier"
            elif key == "line_spacing_rule" and value == "auto" and "line_spacing" not in properties:
                status, reason = "UNVERIFIED", "no_explicit_automatic_spacing_ratio"
            check = {"target": role, "property": key, "expected": value, "status": status}
            if reason:
                check["reason"] = reason
            checks.append(check)
    supported_page = {"width_mm", "height_mm", "margin_top_mm", "margin_bottom_mm", "margin_left_mm", "margin_right_mm", "columns", "column_gap_mm", "mirror_margins"}
    for key, value in profile.get("page", {}).items():
        status = "FAIL" if not exact else "PASS" if key in supported_page else "UNVERIFIED"
        check = {"target": "page", "property": key, "expected": value, "status": status}
        if status == "UNVERIFIED":
            check["reason"] = "header_coordinate_projection" if key in {"header_distance_mm", "footer_distance_mm"} else "page_property_not_implemented"
        checks.append(check)
    for role, properties in (profile.get("running") or {}).items():
        for key, value in properties.items():
            checks.append({"target": role, "property": key, "expected": value,
                           "status": "FAIL" if not exact else "UNVERIFIED", "reason": "source_header_or_footer_requires_rendered_check"})
    if profile.get("tables"):
        checks.append({"target": "table", "property": "borders", "status": "UNVERIFIED" if exact else "FAIL",
                       "reason": "native_table_structure_not_rewritten"})
    if profile.get("sections"):
        checks.append({"target": "sections", "property": "body_starts_at", "status": "UNVERIFIED" if exact else "FAIL",
                       "reason": "native_word_section_boundary_not_applied_to_latex"})
    states = {check["status"] for check in checks}
    return {"status": "FAIL" if "FAIL" in states else "UNVERIFIED" if "UNVERIFIED" in states else "PASS",
            "checking": "generated_controls_and_document_carriers", "checks": checks}


def apply_latex(source: str | Path, output: str | Path, profile: dict) -> dict:
    from .templates import guard_engine, native_template, install_assets
    guard_engine(profile, "latex")
    root, main, files = _project(source)
    destination = Path(output).resolve()
    if destination.exists():
        raise FileExistsError("Output must be a new project directory")
    if destination == root or root in destination.parents:
        raise ValueError("Output must be outside the source project")
    risks = _risks(root, files)
    if risks:
        raise ValueError(f"Unsafe LaTeX project: {risks}")
    if (root / LAYOUT).exists() and not _managed_layout(root / LAYOUT):
        raise ValueError("Existing layout filename is not a ManuWeave managed file")
    if (root / PREAMBLE).exists() and not _managed_preamble(root / PREAMBLE):
        raise ValueError("Existing pre-class filename is not a ManuWeave managed file")
    if (root / COMPILE_SETTINGS).exists() and not _managed_compile(root / COMPILE_SETTINGS):
        raise ValueError("Existing compile settings are not owned formatting metadata")
    text = _read(main).replace(INJECTION + "\n", "").replace(INJECTION, "").replace(PRE_INJECTION + "\n", "").replace(PRE_INJECTION, "")
    old = CLASS.search(_comments(text))
    config = profile.get("latex", {})
    name = _token(config.get("documentclass", old.group(2)))
    options = config.get("options", [v for v in (old.group(1) or "").split(",") if v])
    options = [_token(v, True) for v in options]
    columns = None if native_template(profile) else profile.get("page", {}).get("columns")
    if columns is not None:
        if columns not in (1, 2):
            raise ValueError("Only one or two columns are supported")
        options = [v for v in options if v not in {"onecolumn", "twocolumn"}]
        options.append("twocolumn" if columns == 2 else "onecolumn")
    declaration = "\\documentclass" + ("[" + ",".join(options) + "]" if options else "") + "{" + name + "}"
    preamble = _preamble(profile, _carrier_text(files))
    prefix = PRE_INJECTION + "\n" if len(preamble) > 1 else ""
    text = text[:old.start()] + prefix + declaration + text[old.end():]
    bibliography_style = config.get("bibliography_style")
    if bibliography_style:
        bibliography_style = _token(bibliography_style)
        text = re.sub(r"\\bibliographystyle\s*\{[^{}]+\}", lambda _: "\\bibliographystyle{" + bibliography_style + "}", text)
        if not re.search(r"\\bibliographystyle\s*\{", text):
            end = re.search(r"\\end\s*\{document\}", _comments(text))
            if end is None:
                raise ValueError("Bibliography formatting requires a document end")
            text = text[:end.start()] + "\\bibliographystyle{" + bibliography_style + "}\n" + text[end.start():]
    layout = _layout(profile, text, _carrier_text(files))
    marker = re.search(r"\\begin\s*\{document\}", _comments(text))
    if marker is None:
        raise ValueError("Main file has no begin{document}")
    text = text[:marker.start()] + INJECTION + "\n" + text[marker.start():]
    destination.mkdir(parents=True)
    try:
        for file in files:
            target = destination / file.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
        template_changes = install_assets(profile, destination)
        (destination / main.relative_to(root)).write_text(text, encoding="utf-8")
        (destination / LAYOUT).write_text(layout, encoding="utf-8")
        if len(preamble) > 1 or (destination / PREAMBLE).exists():
            (destination / PREAMBLE).write_text("\n".join(preamble) + "\n", encoding="utf-8")
        settings = {"format": "manuweave-compile-v1", "engine": config.get("engine") or "auto"}
        from .models import LaTeXRule
        LaTeXRule.model_validate({k: v for k, v in settings.items() if k != "format"}, strict=True)
        (destination / COMPILE_SETTINGS).write_text(json.dumps(settings, indent=2), encoding="utf-8")
        report = audit_latex(source, destination / main.relative_to(root), profile)
        if report["content"] != "PASS":
            raise ValueError("Content audit failed; output rolled back")
    except Exception:
        shutil.rmtree(destination)
        raise
    return {"output": str(destination), "main": main.relative_to(root).as_posix(), "audit": report,
            "changes": ["documentclass", LAYOUT, "preamble_layout_input"] + template_changes}


def audit_latex(before: str | Path, after: str | Path, profile: dict | None = None) -> dict:
    original = inspect_latex(before)
    current = inspect_latex(after)
    errors = []
    left, right = original["inventory"], current["inventory"]
    from .templates import authenticated_asset, native_template, assets
    added = set(right) - set(left)
    expected_assets = {name for _, name in assets(profile)} if profile else set()
    after_root, _, _ = _project(after)
    allowed_additions = {name for name in added if (not profile or name in expected_assets) and authenticated_asset(after_root / name)}
    if set(left) - set(right) or added - allowed_additions:
        errors.append({"code": "file_inventory_changed", "missing": sorted(set(left) - set(right)), "added": sorted(added - allowed_additions)})
    for file in set(left) & set(right):
        if left[file]["content_sha256"] != right[file]["content_sha256"]:
            errors.append({"code": "content_changed", "file": file})
    root, main, project_files = _project(after)
    style = "UNVERIFIED"
    if profile is not None:
        try:
            expected = _layout(profile, _read(main), _carrier_text(project_files))
        except ValueError as error:
            expected = None
            errors.append({"code": "profile_conflict", "message": str(error)})
        layout = root / LAYOUT
        style = "PASS" if expected is not None and layout.is_file() and _read(layout) == expected else "FAIL"
        declaration = CLASS.search(_comments(_read(main)))
        config = profile.get("latex", {})
        if config.get("documentclass") and declaration.group(2) != config["documentclass"]:
            style = "FAIL"
        if any(option not in (declaration.group(1) or "").split(",") for option in config.get("options", [])
               if option not in {"onecolumn", "twocolumn"}):
            style = "FAIL"
        columns = None if native_template(profile) else profile.get("page", {}).get("columns")
        if columns and ("twocolumn" if columns == 2 else "onecolumn") not in (declaration.group(1) or "").split(","):
            style = "FAIL"
        if _read(main).count(INJECTION) != 1:
            style = "FAIL"
        expected_preamble = _preamble(profile, _carrier_text(project_files))
        if len(expected_preamble) > 1 or (root / PREAMBLE).exists():
            if (_read(main).count(PRE_INJECTION) != (1 if len(expected_preamble) > 1 else 0)
                    or not _managed_preamble(root / PREAMBLE)
                    or _read(root / PREAMBLE) != "\n".join(expected_preamble) + "\n"):
                style = "FAIL"
        if (root / COMPILE_SETTINGS).exists():
            try:
                settings = _compile_settings(root / COMPILE_SETTINGS)
                if settings.get("engine") != (config.get("engine") or "auto"):
                    style = "FAIL"
            except ValueError:
                style = "FAIL"
        for path, filename in assets(profile):
            if not (root / filename).is_file() or _hash((root / filename).read_bytes()) != _hash(path.read_bytes()):
                style = "FAIL"
        if config.get("bibliography_style"):
            styles = re.findall(r"\\bibliographystyle\s*\{([^{}]+)\}", _uncomment(_read(main)))
            if not styles or any(s != config["bibliography_style"] for s in styles):
                style = "FAIL"
    rule_checks = inspect_applied_rules(after, profile) if profile is not None else None
    if rule_checks and style == "PASS" and rule_checks["status"] != "PASS":
        style = rule_checks["status"]
    return {"content": "FAIL" if errors else "PASS", "style": style, "visual": "UNVERIFIED", "issues": errors,
            "security": "FAIL" if current["risks"] else "PASS", "rule_checks": rule_checks}


def _run_native_tex(command: list[str], directory: Path, environment: dict, timeout: float) -> tuple[int, str, bool]:
    """Run a fixed tool command and terminate only its owned process tree."""
    options = {"cwd": directory, "env": environment, "shell": False, "stdout": subprocess.PIPE,
               "stderr": subprocess.STDOUT, "text": True, "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
        try:
            import resource
        except ImportError:
            resource = None
        if resource is not None:
            def limits():
                resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
                resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
                if hasattr(resource, "RLIMIT_AS"):
                    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))

            options["preexec_fn"] = limits
    process = subprocess.Popen(command, **options)
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output, False
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
            subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"], shell=False,
                           capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            output = "Owned TeX process tree did not close its output pipe after termination."
        return -1, output + "\nCompilation exceeded 90 second resource deadline", True


def _native_tex_engine(requested: str, text: str) -> tuple[str, str | None, str | None]:
    available = {name: shutil.which(name) for name in ("latexmk", "xelatex", "pdflatex", "tectonic", "dvips", "ps2pdf")}
    if requested == "auto":
        if available["latexmk"] and (available["pdflatex"] or available["xelatex"]):
            use_xetex = bool(re.search(r"[\u3400-\u9fff]|\\(?:usepackage|documentclass).*(?:ctex|fontspec|xeCJK)", text)) or not available["pdflatex"]
            requested = "latexmk" if use_xetex and available["xelatex"] else "latexmk-pdf"
        else:
            requested = next((name for name in ("xelatex", "pdflatex", "tectonic") if available[name]), "auto")
    if requested not in {"auto", "latexmk", "latexmk-pdf", "latexmk-ps", "xelatex", "pdflatex", "tectonic"}:
        raise ValueError("Unsupported native TeX engine")
    executable = available.get("latexmk" if requested.startswith("latexmk") else requested)
    if not executable:
        return requested, None, "Requested local TeX executable is not installed"
    if requested in {"latexmk", "latexmk-pdf"}:
        dependency = "xelatex" if requested == "latexmk" else "pdflatex"
        if not available[dependency]:
            return requested, None, f"Required existing tool is unavailable: {dependency}"
    if requested == "latexmk-ps":
        ghostscript = next((shutil.which(name) for name in ("gswin64c", "gswin32c", "gs") if shutil.which(name)), None)
        if not ghostscript and os.name == "nt":
            bundled = Path(executable).parents[2] / "tlpkg" / "tlgs" / "bin" / "gswin64c.exe"
            ghostscript = str(bundled) if bundled.is_file() else None
        if not all((available["dvips"], available["ps2pdf"], ghostscript)):
            return requested, None, "PostScript route requires existing dvips, ps2pdf and Ghostscript; no dependency was installed"
    return requested, executable, None


def compile_latex(source: str | Path, output_dir: str | Path) -> dict:
    root, main, files = _project(source)
    risks = _risks(root, files)
    from .templates import trusted_style_asset
    native_unsafe = re.compile(r"\\(?:special|pdfobj|pdffiledump|pdffilesize|pdfximage|XeTeXpicfile|scantokens|everyjob|endlinechar|escapechar|ExplSyntaxOn|file_[A-Za-z_]*|ior_[A-Za-z_]*)\b")
    for path in files:
        if path.suffix.lower() in TEXT_EXTENSIONS and not trusted_style_asset(path):
            match = native_unsafe.search(_uncomment(_read(path)))
            if match:
                risks.append({"file": path.relative_to(root).as_posix(), "reason": "unsupported_native_file_or_token_primitive", "token": match.group(0)})
    security = {"security": "native_no_shell_escape_strict_preflight", "isolation": "none"}
    if risks:
        return {"status": "FAIL", "reason": "unsafe_project", "issues": risks, **security}
    settings = _compile_settings(root / COMPILE_SETTINGS) if (root / COMPILE_SETTINGS).is_file() else {}
    engine, executable, missing = _native_tex_engine(settings.get("engine") or "auto", _carrier_text(files) + ("\n" + _read(root / LAYOUT) if (root / LAYOUT).is_file() else ""))
    if missing:
        return {"status": "UNVERIFIED", "reason": missing, "engine": engine, **security}
    destination = Path(output_dir).resolve()
    if destination.exists():
        raise FileExistsError("Compilation output directory already exists")
    if destination == root or root in destination.parents:
        raise ValueError("Compilation output must be outside project")
    destination.mkdir(parents=True)
    source_hash = _hash(json.dumps({p.relative_to(root).as_posix(): _hash(p.read_bytes()) for p in files}, sort_keys=True).encode())
    started = time.monotonic()
    logs, commands = [], []
    status, timed_out = "PASS", False
    with tempfile.TemporaryDirectory(prefix="manuweave-native-tex-") as temporary:
        work = Path(temporary) / "project"
        work.mkdir()
        for path in files:
            target = work / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        build = work / "manuweave-build"
        if build.exists():
            raise ValueError("Reserved temporary build directory conflicts with the project")
        build.mkdir()
        environment = os.environ.copy()
        environment.update(openin_any="p", openout_any="p", TEXMFOUTPUT=str(build),
                           TEXMFVAR=str(Path(temporary) / "texmf-var"), TEXMFCONFIG=str(Path(temporary) / "texmf-config"))
        environment["PATH"] = str(Path(executable).parent) + os.pathsep + environment.get("PATH", "")
        # Remove inherited custom input search paths; system TeX resources remain
        # available through the trailing empty component.
        for variable in ("TEXINPUTS", "BIBINPUTS", "BSTINPUTS"):
            environment[variable] = str(work) + "//" + os.pathsep
        native_main = "./" + main.relative_to(root).as_posix()
        if engine == "tectonic":
            command = [executable, "--only-cached", "--untrusted", "--keep-logs", "--keep-intermediates", "--outdir", str(build), native_main]
        elif engine.startswith("latexmk"):
            option = "-pdfps" if engine == "latexmk-ps" else "-pdf" if engine == "latexmk-pdf" else "-xelatex"
            command = [executable, "-norc", option, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-outdir=manuweave-build"]
            if engine == "latexmk-ps":
                command += ["-e", "$dvips = 'dvips -R2 %O -o %D %S'; $ps2pdf = 'ps2pdf -dSAFER %O %S %D';"]
            command.append(native_main)
        else:
            command = [executable, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-output-directory=manuweave-build", native_main]
        try:
            for _ in range(2 if engine in {"xelatex", "pdflatex"} else 1):
                commands.append(command)
                remaining = max(0.1, 90 - (time.monotonic() - started))
                code, output, timed_out = _run_native_tex(command, work, environment, remaining)
                logs.append(output)
                if code:
                    status = "FAIL"
                    break
        except OSError as error:
            status = "UNVERIFIED"
            logs.append(f"Existing local TeX tool could not start: {error}")
        output_files = [path for path in build.rglob("*") if path.is_file()]
        if sum(path.stat().st_size for path in output_files) > MAX_BYTES:
            status = "FAIL"
            logs.append("Generated output exceeds the 128 MiB collection limit")
        else:
            for path in output_files:
                target = destination / path.relative_to(build)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    log = "\n".join(logs)
    (destination / "compile.log").write_text(log, encoding="utf-8")
    issues = [{"code": code, "message": line} for line in log.splitlines()
              for code, pattern in (("overflow", r"Overfull \\[hv]box"), ("font", r"Missing character|Font.*not found"),
                                    ("unresolved_reference", r"undefined references|Citation.*undefined|Reference.*undefined"),
                                    ("rerun_not_converged", r"rerun seems needed|stopping at \d+ passes"),
                                    ("compile_error", r"^!|^error:")) if re.search(pattern, line)]
    native_log = destination / (main.stem + ".log")
    if native_log.is_file():
        final_log = native_log.read_text(encoding="utf-8", errors="replace")
        # Both execution routes include warnings from preliminary passes.
        # Only the final native log establishes unresolved references.
        issues = [i for i in issues if i["code"] not in {"unresolved_reference", "rerun_not_converged"}]
        issues.extend({"code": "unresolved_reference", "message": line} for line in final_log.splitlines()
                      if re.search(r"undefined references|Citation.*undefined|Reference.*undefined", line))
        for line in final_log.splitlines():
            if re.search(r"LaTeX Font Warning: Font shape .*(?:undefined|not available)|Some font shapes were not available|Size substitutions with differences", line):
                issues.append({"code": "font_substitution", "message": line, "source": str(native_log)})
    from .templates import classify_native_diagnostic
    issues = [classify_native_diagnostic(root, main, issue) for issue in issues]
    pdf = destination / (main.stem + ".pdf")
    if status != "UNVERIFIED" and (not pdf.is_file() or any(issue.get("severity") != "review" for issue in issues)):
        status = "FAIL"
    report = {"status": status, "pdf": str(pdf) if pdf.is_file() else None, "log": str(destination / "compile.log"),
            "issues": issues, "visual": "UNVERIFIED", "source_sha256": source_hash,
            "native_log": str(native_log) if native_log.is_file() else None, "engine": engine,
            "layout_status": "UNVERIFIED" if not pdf.is_file() or any(i.get("severity") == "review" for i in issues) else "FAIL" if any(i["code"] == "overflow" for i in issues) else "PASS",
            "elapsed_seconds": round(time.monotonic() - started, 3), "timed_out": timed_out,
            "commands": commands, "timeout_seconds": 90, **security}
    (destination / "compile-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def convert(source: str | Path, output: str | Path) -> dict:
    """Explicit conversion only; loss assessment remains required after conversion."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or output == source:
        raise FileExistsError("Conversion output must be new")
    if {source.suffix.lower(), output.suffix.lower()} != {".docx", ".tex"}:
        raise ValueError("Only explicit DOCX/LaTeX conversion is supported")
    pandoc = shutil.which("pandoc")
    if not pandoc:
        try:
            import pypandoc
            pandoc = pypandoc.get_pandoc_path()
        except (ImportError, OSError):
            return {"status": "UNVERIFIED", "reason": "Pandoc is not installed; install the convert extra"}
    if source.suffix.lower() == ".tex":
        root, _, files = _project(source)
        if _risks(root, files):
            raise ValueError("Unsafe LaTeX project")
    else:
        from .word import inspect_docx
        inspect_docx(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    media_name = output.stem + "-media"
    if (output.parent / media_name).exists():
        raise FileExistsError("Conversion media directory already exists")
    with tempfile.TemporaryDirectory(prefix="manuweave-convert-") as temp:
        temp = Path(temp)
        target = temp / output.name
        diagnostics = []
        if source.suffix.lower() == ".tex":
            # Expand only static in-project includes. Never execute TeX or Pandoc filters.
            def expand(path, ancestors=()):
                path = path.resolve()
                if path in ancestors or len(ancestors) > 32:
                    raise ValueError("Cyclic or excessively nested LaTeX includes")
                if root != path and root not in path.parents:
                    raise ValueError("Include escapes project")
                text = _read(path)

                def include(match):
                    child = root / match.group(1)
                    if not child.suffix:
                        child = child.with_suffix(".tex")
                    if not child.is_file():
                        raise ValueError("Missing included source file")
                    return expand(child, ancestors + (path,))

                return re.sub(r"\\(?:input|include)\s*\{([^{}]+)\}", include, text)

            parsed = subprocess.run([pandoc, "--sandbox", "--from=latex", "--to=json"],
                                    input=expand(source), cwd=temp, capture_output=True, text=True, timeout=90)
            if parsed.returncode:
                return {"status": "FAIL", "diagnostic": parsed.stderr}
            import base64
            import json
            import mimetypes
            from PIL import Image
            ast = json.loads(parsed.stdout)
            embedded = []

            def embed(node):
                if isinstance(node, dict):
                    if node.get("t") == "Image":
                        name = node["c"][-1][0]
                        path = (root / name).resolve()
                        if root not in path.parents or not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                            raise ValueError("Conversion image must be a supported local in-project raster image")
                        with Image.open(path) as image:
                            image.verify()
                        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
                        node["c"][-1][0] = "data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode("ascii")
                        embedded.append(name)
                    for child in node.values():
                        embed(child)
                elif isinstance(node, list):
                    for child in node:
                        embed(child)

            embed(ast)
            result = subprocess.run([pandoc, "--sandbox", "--standalone", "--from=json", "--to=docx", "-o", str(target)],
                                    input=json.dumps(ast), cwd=temp, capture_output=True, text=True, timeout=90)
            diagnostics.extend([parsed.stderr, result.stderr])
        else:
            embedded = []
            result = subprocess.run([pandoc, "--sandbox", "--standalone", "--from=docx", "--to=latex",
                                     "--extract-media=" + media_name, str(source), "-o", str(target)],
                                    cwd=temp, capture_output=True, text=True, timeout=90)
            diagnostics.append(result.stderr)
        if result.returncode == 0 and target.is_file():
            with output.open("xb") as stream:
                stream.write(target.read_bytes())
            media = temp / media_name
            if media.exists():
                shutil.copytree(media, output.parent / media_name)
    return {"status": "PASS" if result.returncode == 0 else "FAIL", "output": str(output),
            "diagnostic": "\n".join(diagnostics), "fidelity": "UNVERIFIED", "embedded_images": embedded,
            "media_directory": str(output.parent / media_name) if (output.parent / media_name).exists() else None,
            "losses_to_review": ["custom macros and document styles", "equation representation", "cross references and bibliography fields", "merged tables and floating object placement"]}
