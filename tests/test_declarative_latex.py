"""Exercise JSON-driven layout against real standard-LaTeX document objects."""
from __future__ import annotations

import json
import re
import shutil

import pytest

from manuweave.latex import (
    LAYOUT,
    LAYOUT_COMMENT,
    _managed_layout,
    apply_latex,
    audit_latex,
    compile_latex,
    inspect_applied_rules,
)


def _profile():
    def font(size, baseline, **extra):
        return {"font": "Times", "size_pt": size, "line_spacing_rule": "exact", "line_spacing_pt": baseline, **extra}

    return {
        "rules": {
            "title": font(20, 24, alignment="center", bold=True),
            "subtitle": font(12, 15, alignment="center"),
            "author": font(11, 14, alignment="center"),
            "affiliation": font(9, 11, alignment="center"),
            "correspondence": font(8, 10, alignment="center"),
            "body": font(10, 14, alignment="justify", first_line_pt=7, space_after_pt=2),
            "abstract": font(9, 11, alignment="justify", left_indent_pt=5, right_indent_pt=5),
            "keywords": font(8, 10, alignment="left"),
            "heading1": font(13, 16, bold=True, space_before_pt=8, space_after_pt=4),
            "heading2": font(11, 14, italic=True),
            "equation": font(10, 14, space_before_pt=6, space_after_pt=6),
            "figure_caption": font(8, 10, alignment="center", space_before_pt=4, space_after_pt=2),
            "table_caption": font(9, 11, alignment="center"),
            "table_body": font(9, 11),
            "reference": font(8, 10),
        },
        "page": {"width_mm": 210, "height_mm": 297, "margin_left_mm": 20, "margin_right_mm": 20,
                 "margin_top_mm": 20, "margin_bottom_mm": 20, "columns": 2, "column_gap_mm": 6},
        "latex": {"documentclass": "article", "engine": "pdflatex"},
    }


def _project(tmp_path):
    project = tmp_path / "source"
    project.mkdir()
    (project / "parts").mkdir()
    (project / "parts/method.tex").write_text(
        "\\subsection{SubheadingMarker}\n"
        "BodyMarker: the preserved synthetic value is 0.125.\n"
        "\\begin{equation}E=mc^2\\label{eq:stable}\\end{equation}\n",
        encoding="utf-8",
    )
    (project / "main.tex").write_text(
        r"""\documentclass{article}
\usepackage{amsmath}
\newcommand{\observed}{0.125}
\title{TitleMarker}
\author{AuthorMarker \and SecondAuthor}
\subtitle{SubtitleMarker}
\affiliation{AffiliationMarker}
\correspondence{CorrespondenceMarker}
\date{}
\begin{document}
\typeout{MWCOLUMN=\the\columnwidth;MWGAP=\the\columnsep}
\maketitle
\begin{abstract}AbstractMarker: existing source evidence only.\end{abstract}
\keywords{KeywordsMarker: synthetic material}
\section{HeadingMarker}
\input{parts/method}
\begin{figure}[ht]\centering\rule{20mm}{8mm}\caption{FigureCaptionMarker}\label{fig:stable}\end{figure}
\begin{table}[ht]\caption{TableCaptionMarker}\centering\begin{tabular}{ll}TableBodyMarker&12\\stable&24\\\end{tabular}\end{table}
Equation~\ref{eq:stable}, figure~\ref{fig:stable}, and citation~\cite{fixture} remain native.
\begin{thebibliography}{1}
\bibitem{fixture}ReferenceMarker. A synthetic entry, 2024.
\end{thebibliography}
\end{document}
""",
        encoding="utf-8",
    )
    return project


def test_json_layout_preserves_multifile_source_and_detects_changed_controls(tmp_path):
    source = _project(tmp_path)
    profile = _profile()
    original_child = (source / "parts/method.tex").read_bytes()
    output = tmp_path / "formatted"
    result = apply_latex(source, output, profile)
    assert result["audit"]["content"] == "PASS"
    assert result["audit"]["style"] == "PASS"
    assert (output / "parts/method.tex").read_bytes() == original_child
    assert not list(output.glob("*.cls")) and not list(output.glob("*.sty"))
    assert _managed_layout(output / LAYOUT)
    second = tmp_path / "second"
    assert apply_latex(output, second, profile)["audit"]["style"] == "PASS"
    assert (output / LAYOUT).read_bytes() == (second / LAYOUT).read_bytes()
    layout = output / LAYOUT
    layout.write_text(layout.read_text(encoding="utf-8").replace(r"\fontsize{20bp}", r"\fontsize{18bp}"), encoding="utf-8")
    assert not _managed_layout(layout)
    damaged = audit_latex(source, output, profile)
    assert damaged["content"] == "FAIL" and damaged["style"] == "FAIL"


def test_declared_json_does_not_make_unknown_source_controls_trusted(tmp_path):
    source = _project(tmp_path)
    output = tmp_path / "formatted"
    apply_latex(source, output, _profile())
    layout = output / LAYOUT
    lines = layout.read_text(encoding="utf-8").splitlines()
    configuration = json.loads(lines[1][len(LAYOUT_COMMENT):])
    configuration["rules"]["body"]["font"] = r"Times}\input{private}"
    lines[1] = LAYOUT_COMMENT + json.dumps(configuration, separators=(",", ":"))
    layout.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not _managed_layout(layout)
    with pytest.raises(ValueError, match="Existing layout"):
        apply_latex(output, tmp_path / "rejected", _profile())
    assert not (tmp_path / "rejected").exists()


def test_single_line_projects_keep_content_hash_when_layout_is_inserted(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    main = source / "main.tex"
    main.write_text(r"\documentclass{article}\title{Title}\author{Author}\begin{document}\maketitle Value 0.125.\end{document}", encoding="utf-8")
    profile = {"rules": {"title": {"size_pt": 18, "alignment": "center"}, "author": {"size_pt": 10}}}
    result = apply_latex(source, tmp_path / "formatted", profile)
    assert result["audit"]["content"] == "PASS"
    assert result["audit"]["style"] == "PASS"


def test_grid_and_custom_carriers_are_not_counted_as_applied_formats(tmp_path):
    source = _project(tmp_path)
    main = source / "main.tex"
    main.write_text(main.read_text(encoding="utf-8").replace(r"\title{TitleMarker}", r"\renewcommand{\maketitle}{CustomTitleMarker}\title{TitleMarker}"), encoding="utf-8")
    profile = _profile()
    profile["page"]["grid_type"] = "lines"
    profile["page"]["grid_line_pitch_pt"] = 15.6
    output = tmp_path / "formatted"
    result = apply_latex(source, output, profile)
    assert result["audit"]["content"] == "PASS"
    assert result["audit"]["style"] == "UNVERIFIED"
    checks = inspect_applied_rules(output, profile)["checks"]
    assert any(check["target"] == "title" and check["reason"] == "source_defines_custom_title_carrier" for check in checks if check.get("reason"))
    assert any(check["property"] == "grid_type" and check["status"] == "UNVERIFIED" for check in checks)


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="An existing pdflatex is required for physical PDF measurements")
def test_real_pdf_has_source_preserved_objects_and_rule_selected_sizes(tmp_path):
    source = _project(tmp_path)
    output = tmp_path / "formatted"
    apply_latex(source, output, _profile())
    compiled = compile_latex(output, tmp_path / "render")
    assert compiled["status"] == "PASS", compiled
    import pypdfium2 as pdfium
    from pypdfium2 import raw

    expected = {"TitleMarker": 20, "SubtitleMarker": 12, "AuthorMarker": 11, "AffiliationMarker": 9,
                "CorrespondenceMarker": 8, "AbstractMarker": 9, "KeywordsMarker": 8,
                "HeadingMarker": 13, "SubheadingMarker": 11, "BodyMarker": 10,
                "FigureCaptionMarker": 8, "TableCaptionMarker": 9, "TableBodyMarker": 9, "ReferenceMarker": 8}
    found = {}
    with pdfium.PdfDocument(tmp_path / "render/main.pdf") as document:
        assert len(document) >= 1
        page = document[0]
        assert page.get_size() == pytest.approx((210 / 25.4 * 72, 297 / 25.4 * 72), abs=.02)
        page.close()
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            for needle in expected:
                search = textpage.search(needle, match_case=True)
                match = search.get_next()
                if match:
                    found[needle] = raw.FPDFText_GetFontSize(textpage.raw, match[0])
                search.close()
            textpage.close()
            page.close()
    assert found.keys() == expected.keys()
    assert found == pytest.approx(expected, abs=.04)
    # Both links resolve in the real compiler rather than merely surviving text edits.
    log = (tmp_path / "render/main.log").read_text(encoding="utf-8", errors="replace")
    assert not re.search(r"undefined references|Citation.*undefined|Reference.*undefined", log)
    dimensions = re.search(r"MWCOLUMN=([0-9.]+)pt;MWGAP=([0-9.]+)pt", log)
    assert dimensions
    column_mm, gap_mm = (float(value) * 25.4 / 72.27 for value in dimensions.groups())
    assert column_mm == pytest.approx(82, abs=.01)
    assert gap_mm == pytest.approx(6, abs=.01)


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="An existing TeX installation is required")
def test_tex_distribution_font_families_do_not_require_system_installation(tmp_path):
    source = _project(tmp_path)
    profile = _profile()
    profile["rules"]["body"]["font"] = "Linux Libertine"
    profile["rules"]["title"]["font"] = "Linux Biolinum"
    profile["rules"]["reference"]["font"] = "STIX Two Text"
    output = tmp_path / "formatted"
    apply_latex(source, output, profile)
    compiled = compile_latex(output, tmp_path / "render")
    assert compiled["status"] == "PASS", compiled
    import ctypes
    import pypdfium2 as pdfium
    from pypdfium2 import raw

    expected = {"TitleMarker": "biolinum", "BodyMarker": "libertine", "ReferenceMarker": "stix"}
    observed = {}
    with pdfium.PdfDocument(tmp_path / "render/main.pdf") as document:
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            for needle in expected:
                search = textpage.search(needle, match_case=True)
                match = search.get_next()
                if match:
                    flags = ctypes.c_int()
                    length = raw.FPDFText_GetFontInfo(textpage.raw, match[0], None, 0, ctypes.byref(flags))
                    buffer = ctypes.create_string_buffer(length)
                    raw.FPDFText_GetFontInfo(textpage.raw, match[0], buffer, length, ctypes.byref(flags))
                    observed[needle] = buffer.value.decode("utf-8").casefold()
                search.close()
            textpage.close()
            page.close()
    assert observed.keys() == expected.keys()
    assert all(family in observed[needle] for needle, family in expected.items())


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="An existing TeX installation is required")
def test_custom_format_macros_keep_their_rendered_scientific_text(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.tex").write_text(
        r"""\documentclass{article}
\makeatletter
\renewcommand{\@maketitle}{\par TitleMacroValue 0.125.\par}
\makeatother
\renewenvironment{abstract}{\par AbstractMacroValue 42.\begin{quote}}{\end{quote}}
\title{Title stored in the original source}
\author{Original author}
\begin{document}
\maketitle
\begin{abstract}Original abstract evidence.\end{abstract}
\end{document}
""", encoding="utf-8")
    profile = {"rules": {"title": {"font": "Times", "size_pt": 20}, "abstract": {"font": "Times", "size_pt": 9}}}
    output = tmp_path / "formatted"
    result = apply_latex(source, output, profile)
    assert result["audit"]["content"] == "PASS"
    assert result["audit"]["style"] == "UNVERIFIED"
    compiled = compile_latex(output, tmp_path / "render")
    assert compiled["status"] == "PASS", compiled
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(tmp_path / "render/main.pdf") as document:
        contents = []
        for index in range(len(document)):
            page = document[index]
            textpage = page.get_textpage()
            contents.append(textpage.get_text_range())
            textpage.close()
            page.close()
    rendered = " ".join(contents)
    assert "TitleMacroValue 0.125." in rendered
    assert "AbstractMacroValue 42." in rendered
    assert "Original abstract evidence." in rendered
