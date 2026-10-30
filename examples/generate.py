"""Create local synthetic documents for repeatable ManuWeave acceptance checks.

Run from any directory: python examples/generate.py --output examples/generated
The documents contain invented fixture data, never research evidence.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Mm, Pt
from lxml import etree
from PIL import Image, ImageDraw


FIXED_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _font(run, size=11, *, bold=False, east_asia="宋体"):
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._r.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:eastAsia"), east_asia)


def _paragraph(doc, text, *, formatted=False, role="body"):
    # Intentionally leave every paragraph on Normal. The reference challenges
    # effective-format extraction instead of only named-style lookup.
    p = doc.add_paragraph()
    run = p.add_run(text)
    if formatted:
        if role == "title":
            _font(run, 18, bold=True, east_asia="黑体")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(12)
        elif role == "heading1":
            _font(run, 14, bold=True, east_asia="黑体")
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True
        elif role == "heading2":
            _font(run, 12, bold=True)
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(6)
        elif role in {"abstract", "keywords", "reference", "caption"}:
            _font(run, 10)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(3)
            if role == "caption":
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            _font(run)
            p.paragraph_format.line_spacing = 1.5
            p.paragraph_format.first_line_indent = Pt(22)
            p.paragraph_format.space_after = Pt(6)
    else:
        _font(run, 10, east_asia="等线")
        p.paragraph_format.line_spacing = 1.0
    return p


def _figure(path: Path):
    image = Image.new("RGB", (720, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(70, 25), (70, 250), (680, 250)], fill="black", width=3)
    points = [(90, 220), (220, 180), (350, 155), (480, 100), (610, 75)]
    draw.line(points, fill="#244e78", width=5)
    for x, y in points:
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="#244e78")
    draw.text((95, 25), "SYNTHETIC FIXTURE / NOT RESEARCH DATA", fill="black")
    image.save(path)


def _equation(doc):
    p = doc.add_paragraph()
    math = etree.Element(f"{{{M}}}oMathPara", nsmap={"m": M})
    omath = etree.SubElement(math, f"{{{M}}}oMath")
    run = etree.SubElement(omath, f"{{{M}}}r")
    etree.SubElement(run, f"{{{M}}}t").text = "E = mc²"
    p._p.append(math)


def _cross_reference(doc):
    p = doc.add_paragraph()
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), "17")
    start.set(qn("w:name"), "fixture_result")
    p._p.append(start)
    p.add_run("合成结果标记 SYNTHETIC_RESULT_12")
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), "17")
    p._p.append(end)
    ref = doc.add_paragraph("交叉引用：")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), " REF fixture_result \\h ")
    r = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "合成结果标记 SYNTHETIC_RESULT_12"
    r.append(text)
    field.append(r)
    ref._p.append(field)


def _footnote_reference(doc):
    p = doc.add_paragraph("脚注关联保真示例。")
    r = p.add_run()._r
    reference = OxmlElement("w:footnoteReference")
    reference.set(qn("w:id"), "1")
    r.append(reference)


def _package(doc, path: Path, *, footnotes=False):
    doc.core_properties.author = "ManuWeave synthetic fixture"
    doc.core_properties.last_modified_by = "ManuWeave"
    doc.core_properties.created = FIXED_DATE
    doc.core_properties.modified = FIXED_DATE
    data = BytesIO()
    doc.save(data)
    with ZipFile(BytesIO(data.getvalue())) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    if footnotes:
        root = etree.Element(f"{{{W}}}footnotes", nsmap={"w": W})
        for identifier, kind in [(-1, "separator"), (0, "continuationSeparator")]:
            note = etree.SubElement(root, f"{{{W}}}footnote")
            note.set(f"{{{W}}}id", str(identifier))
            note.set(f"{{{W}}}type", kind)
            p = etree.SubElement(note, f"{{{W}}}p")
            r = etree.SubElement(p, f"{{{W}}}r")
            etree.SubElement(r, f"{{{W}}}{kind}")
        note = etree.SubElement(root, f"{{{W}}}footnote")
        note.set(f"{{{W}}}id", "1")
        p = etree.SubElement(note, f"{{{W}}}p")
        r = etree.SubElement(p, f"{{{W}}}r")
        etree.SubElement(r, f"{{{W}}}t").text = "仅用于测试；不代表真实实验。"
        parts["word/footnotes.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
        rels = etree.fromstring(parts["word/_rels/document.xml.rels"])
        rel = etree.SubElement(rels, f"{{{REL}}}Relationship")
        rel.set("Id", "rIdFixtureFootnote")
        rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes")
        rel.set("Target", "footnotes.xml")
        parts["word/_rels/document.xml.rels"] = etree.tostring(rels, xml_declaration=True, encoding="UTF-8")
        types = etree.fromstring(parts["[Content_Types].xml"])
        override = etree.SubElement(types, f"{{{CT}}}Override")
        override.set("PartName", "/word/footnotes.xml")
        override.set("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml")
        parts["[Content_Types].xml"] = etree.tostring(types, xml_declaration=True, encoding="UTF-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name in sorted(parts):
            info = ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, parts[name])


def _word_target(path: Path, image: Path):
    doc = Document()
    doc.sections[0].top_margin = Mm(15)
    doc.sections[0].left_margin = Mm(15)
    _paragraph(doc, "合成文档排版保真验证")
    _paragraph(doc, "本文件完全使用合成内容，仅用于软件验证，不代表真实研究或实验。")
    _paragraph(doc, "1 引言")
    _paragraph(doc, "本测试原稿包含 12 个合成观测值，目标是验证文档对象在排版前后保持完整。")
    _paragraph(doc, "This synthetic manuscript checks native document preservation across formatting operations.")
    _paragraph(doc, "2 方法")
    _paragraph(doc, "2.1 对象清单")
    _paragraph(doc, "原稿对象包括公式、图片、合并单元格、脚注、书签和交叉引用。所有对象均用于软件测试。")
    _equation(doc)
    table = doc.add_table(rows=4, cols=3)
    table.cell(0, 0).merge(table.cell(0, 2)).text = "合成测试表"
    for index, row in enumerate([("组别", "数量", "标记"), ("A", "12", "fixture-a"), ("B", "24", "fixture-b")], 1):
        for col, value in enumerate(row):
            table.cell(index, col).text = value
    table.cell(2, 0).merge(table.cell(3, 0))
    doc.add_picture(str(image), width=Inches(4.5))
    _paragraph(doc, "3 结果")
    _paragraph(doc, "测试数据固定包含数值 12、24 和 0.125，任何未经授权的变化均应触发完整性失败。")
    _cross_reference(doc)
    _footnote_reference(doc)
    _paragraph(doc, "4 结论")
    _paragraph(doc, "该合成文档用于检验结构与对象保留，不支持任何学术结论。")
    # Abstract, keywords, table of contents and figure/table captions are
    # intentionally absent for the completeness-analysis example.
    _package(doc, path, footnotes=True)


def _word_reference(path: Path, image: Path):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Mm(25.4)
    section.left_margin = section.right_margin = Mm(25.4)
    section.header.paragraphs[0].text = "REFERENCE_HEADER_MUST_NOT_LEAK"
    section.footer.paragraphs[0].text = "REFERENCE_FOOTER_MUST_NOT_LEAK"
    _paragraph(doc, "参考版式示例论文", formatted=True, role="title")
    _paragraph(doc, "摘要：REFERENCE_ONLY_ABSTRACT。本段只用于提取摘要版式。", formatted=True, role="abstract")
    _paragraph(doc, "关键词：参考版式；直接格式；合成样例", formatted=True, role="keywords")
    _paragraph(doc, "1 引言", formatted=True, role="heading1")
    for text in [
        "REFERENCE_ONLY_BODY_ALPHA。此处采用手工直接格式设置正文，不依赖样式名称。",
        "REFERENCE_ONLY_BODY_BETA。多段正文为样式学习提供一致的行距和缩进证据。",
        "REFERENCE_ONLY_BODY_GAMMA. Multiple reference paragraphs establish a dominant effective body format.",
    ]:
        _paragraph(doc, text, formatted=True)
    _paragraph(doc, "2 研究方法", formatted=True, role="heading1")
    _paragraph(doc, "2.1 示范小节", formatted=True, role="heading2")
    _paragraph(doc, "REFERENCE_ONLY_BODY_DELTA。该段的字体字号与前述正文保持一致。", formatted=True)
    _equation(doc)
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "参考对象"
    table.cell(0, 1).text = "示例值"
    table.cell(1, 0).text = "REFERENCE_ONLY_TABLE"
    table.cell(1, 1).text = "999"
    _paragraph(doc, "表 1 参考文档中的合成表", formatted=True, role="caption")
    doc.add_picture(str(image), width=Inches(3.5))
    _paragraph(doc, "图 1 参考文档中的示意图", formatted=True, role="caption")
    _paragraph(doc, "3 结论", formatted=True, role="heading1")
    _paragraph(doc, "REFERENCE_ONLY_BODY_EPSILON。参考内容不应进入目标文档。", formatted=True)
    _paragraph(doc, "参考文献", formatted=True, role="heading1")
    _paragraph(doc, "[1] Synthetic fixture bibliography. Local test material, 2026.", formatted=True, role="reference")
    _package(doc, path)


def _latex(directory: Path, image: Path):
    (directory / "sections").mkdir(parents=True, exist_ok=True)
    (directory / "figures").mkdir(exist_ok=True)
    shutil.copyfile(image, directory / "figures" / "synthetic.png")
    files = {
        "main.tex": r"""\documentclass[11pt]{article}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amsthm}
\newtheorem{proposition}{Proposition}
\newcommand{\fixturecount}{12}
\title{Synthetic Manuscript Preservation Fixture}
\author{Synthetic Fixture Author}
\begin{document}
\maketitle
\begin{abstract}
This document contains synthetic material for testing native project formatting.
It does not report research results.
\end{abstract}
\noindent\textbf{Keywords:} synthetic fixture; document preservation
\input{sections/introduction}
\input{sections/method}
\bibliographystyle{plain}
\bibliography{refs}
\end{document}
""",
        "sections/introduction.tex": r"""\section{Introduction}
This project contains \fixturecount{} synthetic observations and a local fixture citation~\cite{fixture2026}.
The value 0.125 is fixed test data. Figure~\ref{fig:fixture} is a synthetic image.
""",
        "sections/method.tex": r"""\section{Method}
\begin{equation}\label{eq:fixture}
E = mc^2
\end{equation}
\begin{proposition}
The fixture contains native mathematical markup.
\end{proposition}
\begin{table}[ht]
\centering
\begin{tabular}{lr}
Group & Count \\
A & 12 \\
B & 24
\end{tabular}
\caption{Synthetic fixture values.}\label{tab:fixture}
\end{table}
\begin{figure}[ht]
\centering\includegraphics[width=.75\linewidth]{figures/synthetic.png}
\caption{Synthetic diagram, not research data.}\label{fig:fixture}
\end{figure}
""",
        "refs.bib": """@misc{fixture2026,
  author = {Synthetic Fixture Author},
  title = {Synthetic fixture bibliography},
  year = {2026},
  note = {Invented local test material, not a real publication}
}
""",
    }
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")


def generate(output: Path | str) -> dict:
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = output / "synthetic.png"
    _figure(image)
    _word_target(output / "unformatted.docx", image)
    _word_reference(output / "reference.docx", image)
    _latex(output / "latex", image)
    manifest = {
        "synthetic": True,
        "description": "Invented local test material; no research claims or real experimental evidence.",
        "target": "unformatted.docx",
        "reference": "reference.docx",
        "latex_main": "latex/main.tex",
        "expected_target_objects": {
            "omml_equations": 1,
            "tables": 1,
            "images": 1,
            "bookmarks": 1,
            "cross_reference_fields": 1,
            "footnote_references": 1,
            "protected_numbers": ["12", "24", "0.125"],
        },
        "intentionally_missing": ["abstract", "keywords", "toc", "figure_caption", "table_caption"],
        "forbidden_reference_markers": ["REFERENCE_ONLY_", "REFERENCE_HEADER_MUST_NOT_LEAK", "REFERENCE_FOOTER_MUST_NOT_LEAK"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output), **manifest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "generated")
    arguments = parser.parse_args()
    print(json.dumps(generate(arguments.output), ensure_ascii=False, indent=2))
