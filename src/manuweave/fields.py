"""Refresh generated TOC caches using read-only Word layout and precise OOXML edits."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from .io import digest, read_json, write_json
from .render import doctor, word_render_risk
from .word import NS, W, _package, _xml, inspect_docx, audit_docx


def _toc_fields(tree):
    return [f for f in tree.findall(".//w:fldSimple", NS) if re.match(r"^\s*TOC(?:\s|$)", f.get(W + "instr", ""), re.I)]


def _update(source, output, texts):
    parts = _package(source)
    tree = _xml(parts["word/document.xml"])
    fields = _toc_fields(tree)
    if len(fields) != len(texts):
        raise ValueError("Word TOC count disagrees with the native source")
    headings = {b["text"].strip() for b in inspect_docx(source)["blocks"] if b["role"].startswith("heading")}
    changes = []
    for field, text in zip(fields, texts):
        entries = [entry.strip() for entry in re.split(r"[\r\n\v]+", text) if entry.strip()]
        parsed = []
        for entry in entries:
            match = re.fullmatch(r"(.+?)\t([0-9ivxlcdmIVXLCDM]+)", entry)
            if not match or match.group(1).strip() not in headings:
                raise ValueError("TOC result is not a source heading with a valid rendered page number")
            parsed.append((match.group(1).strip(), match.group(2)))
        if not parsed:
            raise ValueError("Word returned an empty TOC; no output written")
        for child in list(field):
            field.remove(child)
        for index, (heading, page) in enumerate(parsed):
            run = etree.SubElement(field, W + "r")
            if index:
                etree.SubElement(run, W + "br")
            etree.SubElement(run, W + "t").text = heading
            etree.SubElement(run, W + "tab")
            etree.SubElement(run, W + "t").text = page
        field.set(W + "dirty", "false")
        changes.append({"operation": "refresh_toc_cache", "entries": [{"heading": h, "page": p} for h, p in parsed]})
    parts["word/document.xml"] = etree.tostring(tree, xml_declaration=True, encoding="UTF-8", standalone=True)
    with Path(output).open("xb") as stream:
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in parts.items():
                archive.writestr(name, data)
    report = audit_docx(source, output)
    if report["content"]["status"] != "PASS":
        Path(output).unlink()
        raise ValueError("TOC update damaged protected content; candidate rolled back")
    return changes


def refresh_fields(source, output, max_rounds=3):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output:
        raise FileExistsError("Field-refresh output must be a new DOCX path")
    if source.suffix.lower() != ".docx" or output.suffix.lower() != ".docx":
        raise ValueError("Field refresh only supports DOCX")
    if not 1 <= max_rounds <= 3:
        raise ValueError("TOC refresh limit must be 1..3")
    reason = word_render_risk(source)
    if reason:
        return {"status": "UNVERIFIED", "reason": reason}
    if not doctor()["renderers"]["word_automation"]:
        return {"status": "UNVERIFIED", "reason": "Word automation is required for real TOC page numbers"}
    if not _toc_fields(_xml(_package(source)["word/document.xml"])):
        return {"status": "NOT_APPLICABLE", "reason": "No supported native simple TOC field"}
    changes, previous, current = [], None, source
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="manuweave-fields-") as temp:
        temp = Path(temp)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        for iteration in range(max_rounds):
            cache = temp / f"cache-{iteration}.json"
            result = subprocess.run([sys.executable, "-m", "manuweave.render", str(current), str(temp / f"layout-{iteration}.pdf"), str(cache)],
                                    env=environment, capture_output=True, text=True, errors="replace", timeout=90)
            if result.returncode or not cache.exists():
                return {"status": "FAIL", "reason": "Word TOC calculation failed", "diagnostic": result.stderr[-4000:]}
            texts = read_json(cache)["tables_of_contents"]
            candidate = temp / f"refreshed-{iteration}.docx"
            changes = _update(current, candidate, texts)
            if previous == texts:
                with output.open("xb") as stream:
                    stream.write(candidate.read_bytes())
                report = {"status": "PASS", "output": str(output), "rounds": iteration + 1,
                          "source_sha256": digest(source), "output_sha256": digest(output), "changes": changes,
                          "integrity": audit_docx(source, output)["content"], "renderer": "Microsoft Word read-only layout"}
                write_json(output.with_suffix(".docx.fields.json"), report)
                return report
            previous, current = texts, candidate
    return {"status": "FAIL", "reason": "TOC page numbers did not converge within the bounded refresh limit", "output": None}
