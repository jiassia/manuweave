"""Real local rendering; heuristic geometry checks do not imply full visual acceptance."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .io import digest, write_json


def doctor() -> dict:
    import importlib.util
    word = False
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
                word = True
        except OSError:
            pass
    return {"python": sys.version.split()[0], "dependencies": {
        name: bool(importlib.util.find_spec(name)) for name in
        ["docx", "lxml", "pydantic", "pylatexenc", "pypdfium2", "PIL"]},
        "renderers": {"word_registered": word, "word_automation": word and bool(importlib.util.find_spec("win32com")),
                      "libreoffice": os.environ.get("MANUWEAVE_SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice"),
                      "latexmk": shutil.which("latexmk"), "xelatex": shutil.which("xelatex"),
                      "pdflatex": shutil.which("pdflatex"), "tectonic": shutil.which("tectonic"),
                      "pandoc": shutil.which("pandoc")},
        "policy": "Use existing local tools and fonts. Native TeX disables shell escape and blocks unsafe projects; renderer availability is not visual acceptance."}


def _word_export(source: Path, pdf: Path, fields_output: Path | None = None):
    # Executed in a child so a renderer timeout cannot stall an agent indefinitely.
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    app = None
    document = None
    try:
        app = win32com.client.DispatchEx("Word.Application")
        app.Visible = False
        app.DisplayAlerts = 0
        app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        app.Options.UpdateLinksAtOpen = False
        document = app.Documents.Open(str(source), ConfirmConversions=False, ReadOnly=True,
                                      AddToRecentFiles=False, Visible=False, OpenAndRepair=False,
                                      NoEncodingDialog=True)
        if fields_output is not None:
            document.Repaginate()
            # Query the actual current layout, without replacing the native TOC
            # with Word-generated paragraphs or altering any field instruction.
            headings = [(p.Range.Text.rstrip("\r\x07"), p.Range.Information(1))
                        for p in document.Paragraphs if 1 <= p.OutlineLevel <= 6]
            text = "\r".join(f"{title}\t{page}" for title, page in headings)
            write_json(fields_output, {"tables_of_contents": [text for _ in document.TablesOfContents]})
        document.ExportAsFixedFormat(str(pdf), 17, OpenAfterExport=False)
    finally:
        if document is not None:
            document.Close(False)
        if app is not None:
            app.Quit(False)
        pythoncom.CoUninitialize()


def inspect_pdf(pdf: Path, output: Path) -> dict:
    import pypdfium2 as pdfium
    pages, issues = [], []
    with pdfium.PdfDocument(pdf) as doc:
        for index in range(len(doc)):
            page = doc[index]
            width, height = page.get_size()
            image_path = output / f"page-{index + 1}.png"
            bitmap = page.render(scale=1.5)
            bitmap.to_pil().save(image_path)
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            outside = []
            for char in range(textpage.count_chars()):
                left, bottom, right, top = textpage.get_charbox(char)
                if right > width + 1 or top > height + 1 or left < -1 or bottom < -1:
                    outside.append(char)
            if outside:
                issues.append({"page": index + 1, "code": "text_outside_page", "count": len(outside)})
            if not text.strip():
                issues.append({"page": index + 1, "code": "no_extractable_text", "severity": "review"})
            pages.append({"page": index + 1, "width_pt": width, "height_pt": height,
                          "text_characters": len(text), "png": str(image_path), "sha256": digest(image_path)})
            textpage.close()
            bitmap.close()
            page.close()
    return {"geometry": "FAIL" if any(i["code"] == "text_outside_page" for i in issues) else "PASS",
            "pages": pages, "issues": issues,
            "status": "UNVERIFIED", "reason": "Page images require host visual inspection for overlaps, glyphs, floating objects and orphan headings."}


def word_render_risk(source):
    from .word import _package, _xml, NS
    import re
    parts = _package(source)
    for name, data in parts.items():
        if name.startswith("word/") and name.endswith(".xml"):
            tree = _xml(data)
            instructions = "".join(tree.xpath("//w:instrText/text() | //w:fldSimple/@w:instr", namespaces=NS))
            if re.search(r"\b(DDE|DDEAUTO|INCLUDETEXT|INCLUDEPICTURE|LINK|DATABASE)\b", instructions, re.I):
                return "Active external Word fields are blocked from rendering"
        if name.endswith(".rels"):
            rels = _xml(data)
            if any(el.get("TargetMode") == "External" and not el.get("Type", "").endswith("/hyperlink") for el in rels):
                return "External resource relationships are blocked from rendering"
    return None


def render(source: str | Path, output: str | Path, profile: dict | None = None, renderer: str = "auto") -> dict:
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError("Render output must be a new directory")
    if renderer not in {"auto", "word", "libreoffice"}:
        raise ValueError("Unknown renderer")
    if source.is_dir() and (output == source or source in output.parents):
        raise ValueError("Render output must be outside the source project")
    if source.suffix.lower() == ".tex" or source.is_dir():
        from .latex import compile_latex
        report = compile_latex(source, output)
        if report.get("pdf"):
            report["visual"] = inspect_pdf(Path(report["pdf"]), output)
        return report
    if source.suffix.lower() not in {".docx", ".pdf"}:
        raise ValueError("Expected DOCX, PDF or native LaTeX project")
    if source.suffix.lower() == ".docx":
        reason = word_render_risk(source)
        if reason:
            return {"status": "UNVERIFIED", "reason": reason}
        if renderer == "libreoffice" or not doctor()["renderers"]["word_automation"]:
            if renderer == "word":
                return {"status": "UNVERIFIED", "reason": "Microsoft Word automation is unavailable"}
            from .libreoffice import export_pdf
            report = export_pdf(source, output)
            if report.get("pdf"):
                report.update(source_sha256=digest(source), visual=inspect_pdf(Path(report["pdf"]), output))
                if profile:
                    from .fonts import audit_rendered_fonts
                    report["fonts"] = audit_rendered_fonts(source, report["pdf"], profile)
                write_json(output / "render.json", report)
            return report
    output.mkdir(parents=True)
    pdf = output / (source.stem + ".pdf")
    if source.suffix.lower() == ".pdf":
        shutil.copyfile(source, pdf)
    else:
        try:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
            result = subprocess.run([sys.executable, "-m", "manuweave.render", str(source), str(pdf)],
                                    env=environment, capture_output=True, text=True, errors="replace", timeout=90)
            (output / "renderer.log").write_text(result.stdout + result.stderr, encoding="utf-8")
            if result.returncode or not pdf.exists():
                return {"status": "FAIL", "reason": "Word export failed", "diagnostic": result.stderr[-4000:]}
        except subprocess.TimeoutExpired:
            return {"status": "FAIL", "reason": "Word export exceeded 90 seconds"}
    report = {"status": "PASS", "pdf": str(pdf), "source_sha256": digest(source),
              "renderer": "Microsoft Word" if source.suffix.lower() == ".docx" else "PDFium",
              "visual": inspect_pdf(pdf, output)}
    if profile and source.suffix.lower() == ".docx":
        from .fonts import audit_rendered_fonts
        report["fonts"] = audit_rendered_fonts(source, pdf, profile)
        if renderer == "auto" and report["fonts"]["status"] == "FAIL":
            from .libreoffice import available, export_pdf
            if available()["status"] == "PASS":
                fallback = export_pdf(source, output / "libreoffice")
                if fallback.get("pdf"):
                    fallback["fonts"] = audit_rendered_fonts(source, fallback["pdf"], profile)
                    if fallback["fonts"]["status"] == "PASS":
                        fallback["visual"] = inspect_pdf(Path(fallback["pdf"]), output / "libreoffice")
                        fallback["source_sha256"] = digest(source)
                        fallback["renderer_attempts"] = [report, {k: v for k, v in fallback.items() if k != "visual"}]
                        fallback["reason"] = "Word's actual PDF glyph fonts differed from the requested profile; the logged LibreOffice render uses the required fonts. Native DOCX bytes were not changed."
                        report = fallback
                    else:
                        report["fallback_attempt"] = fallback
    write_json(output / "render.json", report)
    return report


if __name__ == "__main__":
    _word_export(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
