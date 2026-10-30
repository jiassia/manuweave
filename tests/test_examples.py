"""Validate that acceptance fixtures actually contain the claimed native objects."""

import importlib.util
from pathlib import Path
from zipfile import ZipFile

from lxml import etree


def _generator():
    path = Path(__file__).resolve().parents[1] / "examples" / "generate.py"
    spec = importlib.util.spec_from_file_location("manuweave_example_generator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate


def test_native_fixture_objects_and_reference_separation(tmp_path):
    _generator()(tmp_path)
    with ZipFile(tmp_path / "unformatted.docx") as archive:
        xml = archive.read("word/document.xml")
        root = etree.fromstring(xml)
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main", "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
        assert len(root.xpath("//m:oMath", namespaces=ns)) == 1
        assert len(root.xpath("//w:tbl", namespaces=ns)) == 1
        assert root.xpath("//w:gridSpan", namespaces=ns)
        assert root.xpath("//w:vMerge", namespaces=ns)
        assert len(root.xpath("//w:drawing", namespaces=ns)) == 1
        assert len(root.xpath("//w:bookmarkStart", namespaces=ns)) == 1
        assert len(root.xpath("//w:fldSimple", namespaces=ns)) == 1
        assert len(root.xpath("//w:footnoteReference", namespaces=ns)) == 1
        assert "word/footnotes.xml" in archive.namelist()
        assert b"footnotes.xml" in archive.read("word/_rels/document.xml.rels")
        assert b"REFERENCE_ONLY_" not in xml
    with ZipFile(tmp_path / "reference.docx") as archive:
        assert b"REFERENCE_ONLY_BODY_ALPHA" in archive.read("word/document.xml")
    main = (tmp_path / "latex" / "main.tex").read_text()
    assert r"\input{sections/introduction}" in main
    assert (tmp_path / "latex" / "sections" / "method.tex").is_file()
    assert (tmp_path / "latex" / "refs.bib").is_file()


def test_fixture_generation_is_repeatable(tmp_path):
    generate = _generator()
    generate(tmp_path / "first")
    generate(tmp_path / "second")
    for name in ["unformatted.docx", "reference.docx", "synthetic.png", "manifest.json"]:
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
