import copy

import pytest

from manuweave import templates
from manuweave.presets import load_preset


@pytest.mark.parametrize("key,value", [
    ("assets", [{"path": "publisher.cls", "sha256": "0" * 64}]),
    ("fixture", "original/template.tex"),
    ("remote_archive", {"url": "https://example.com/template.zip"}),
])
def test_original_template_files_and_downloads_cannot_enter_a_profile(key, value):
    profile = copy.deepcopy(load_preset("ieee-word-a4-2019"))
    profile["template"][key] = value
    with pytest.raises(ValueError, match="JSON rules"):
        templates.validate_template(profile)


def test_no_source_file_can_gain_implicit_publisher_trust(tmp_path):
    file = tmp_path / "publisher.cls"
    file.write_text(r"\ProvidesClass{publisher}\immediate\write18{unsafe}")
    assert not templates.trusted_style_asset(file)
    assert not templates.authenticated_asset(file)


@pytest.mark.parametrize("change", ["missing", "unknown", "different"])
def test_unconfirmed_journal_values_cannot_create_a_document(tmp_path, change):
    from docx import Document
    from manuweave.word import apply_docx

    profile = load_preset("ieee-word-a4-2019")
    matching = [r for r in profile["template"]["requirements"]
                if r["target"] == "body" and r["property"] == "size_pt"]
    assert matching
    if change == "missing":
        profile["template"]["requirements"] = [
            r for r in profile["template"]["requirements"] if r not in matching]
    elif change == "unknown":
        for rule in matching:
            rule.update(certainty="unknown", expected=None)
    else:
        profile["rules"]["body"]["size_pt"] = 14
    source = tmp_path / "source.docx"
    doc = Document()
    doc.add_paragraph("Synthetic protected content: 12.5")
    doc.save(source)
    original = source.read_bytes()
    output = tmp_path / "must-not-exist.docx"
    with pytest.raises(ValueError, match="Unconfirmed journal formatting rule: body.size_pt"):
        apply_docx(source, output, profile)
    assert not output.exists()
    assert source.read_bytes() == original
