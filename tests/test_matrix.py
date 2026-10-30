import json
from pathlib import Path

import pytest

from manuweave import matrix


def test_tex_probes_use_actual_values_and_units():
    log = "MW_BODY_SIZE_PT=9.535625\nMW_BODY_FONT_FAMILY=ppl\nMW_BODY_FONT_NAME=pplr7t at 9.535625pt\nMW_COLUMNS=2\nMW_PAPER_WIDTH_PT=614.295pt\n"
    parsed = matrix.parse_tex_metrics(log)
    report = matrix.compare_tex_metrics(parsed, {"body_size_pt": 9.535625, "body_font_family": "ppl", "columns": 2, "paper_width_pt": 614.295})
    assert report["status"] == "PASS"
    assert matrix.compare_tex_metrics(parsed, {"body_size_pt": 9.5, "size_tolerance_pt": .02})["status"] == "FAIL"
    assert matrix.compare_tex_metrics(parsed, {"paper_height_pt": 794.97})["status"] == "UNVERIFIED"
    assert matrix.compare_tex_metrics(matrix.parse_tex_metrics(log + "MW_COLUMNS=1\n"), {"columns": 1})["status"] == "FAIL"


def test_reference_order_ignores_narrative_mentions():
    text = "The narrative cites Zulu first and Alpha second.\nReferences\nSynthetic Alpha test reference.\nSynthetic Zulu test reference."
    assert matrix.reference_order(text, ["Alpha", "Zulu"])["status"] == "PASS"
    assert matrix.reference_order(text, ["Zulu", "Alpha"])["status"] == "FAIL"
    assert matrix.reference_order("References absent", ["Alpha", "Zulu"])["status"] == "UNVERIFIED"
    revtex = "The narrative cites Zulu then Alpha.\n1Alpha, S., Invented Fixture Journal 2, 42 (2025).\n2S. Zulu, Invented Fixture Journal 1, 12 (2026)."
    assert matrix.reference_order(revtex, ["Alpha", "Zulu"])["status"] == "PASS"


def test_unprescribed_font_metrics_do_not_invent_a_requirement():
    assert matrix.compare_word_metrics({}, {"rules": {"body": {"line_spacing": 2}}})["status"] == "NOT_APPLICABLE"
    assert matrix.compare_word_metrics({}, {"rules": {"body": {"font": "Arial"}}})["status"] == "UNVERIFIED"
    measured = {"occurrences": [{"glyphs": [{"font_name": "Calibri", "size_pt": 11}]}]}
    assert matrix.compare_word_metrics(measured, {"rules": {"body": {"font": "Arial"}}})["status"] == "FAIL"


def test_final_log_font_substitution_is_a_failure_issue():
    issues = matrix._log_issues("LaTeX Font Warning: Font shape `TU/ptm/m/n' undefined\nSome font shapes were not available, defaults substituted.")
    assert issues
    assert all(issue["code"] == "font_substitution" for issue in issues)


def test_every_real_overflow_remains_a_failure_without_original_template_exceptions():
    for message in (r"Overfull \hbox (123.62721pt too wide) detected at line 10", r"Overfull \hbox (0.15149pt too wide) in paragraph at lines 12--12"):
        issues = matrix._log_issues(message)
        assert issues[0]["code"] == "overflow"
        assert issues[0].get("severity") != "review"


def _pdf(path: Path):
    # A real valid PDF with Type1 text, tested through the actual PDFium API.
    stream = b"BT /F1 10 Tf 50 700 Td (MWBODY Synthetic test) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data)
    data += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    path.write_bytes(data)


def test_real_pdfium_font_and_size_measurement(tmp_path):
    pdf = tmp_path / "font.pdf"
    _pdf(pdf)
    measured = matrix.pdf_body_metrics(pdf)
    glyphs = measured["occurrences"][0]["glyphs"]
    assert all(g["size_pt"] == 10 for g in glyphs)
    assert all(g["font_name"] == "Times-Roman" for g in glyphs)
    assert matrix.compare_word_metrics(measured, {"rules": {"body": {"size_pt": 10, "font": "Times-Roman"}}})["status"] == "PASS"
    assert matrix.compare_word_metrics(measured, {"rules": {"body": {"size_pt": 9.5}}})["status"] == "FAIL"
    boundary = {"occurrences": [{"glyphs": [{"size_pt": 10.5600004196167, "font_name": "TimesNewRomanPSMT"}]}]}
    assert matrix.compare_word_metrics(boundary, {"rules": {"body": {"size_pt": 10.5}}})["status"] == "PASS"


def test_pdf_boxes_are_recorded_separately_from_nominal_paper_probe(tmp_path):
    pdf = tmp_path / "boxes.pdf"
    _pdf(pdf)
    report = matrix.pdf_page_boxes(pdf, {"paper_width_pt": 614.295, "paper_height_pt": 794.97})
    assert report["measurement_status"] == "PASS"
    assert report["physical_equivalence_status"] == "UNVERIFIED"
    assert report["pages"][0]["MediaBox"] == (0, 0, 612, 792)
    assert report["pages"][0]["CropBox"] is None
    assert report["pages"][0]["TrimBox"] is None
    assert report["pages"][0]["BleedBox"] is None
    assert abs(report["pages"][0]["nominal_paper_comparison"]["width"]["delta_bp"]) < 1e-6


def test_chinese_font_identity_requires_actual_cjk_glyph_measurement():
    profile = {"rules": {"body": {"size_pt": 10.5, "east_asia_font": "宋体"}}}
    measured = {"occurrences": [{"glyphs": [{"size_pt": 10.56, "font_name": "TimesNewRomanPSMT"}]}]}
    assert matrix.compare_word_metrics(measured, profile)["status"] == "UNVERIFIED"
    measured["east_asia"] = {"occurrences": [{"glyphs": [{"size_pt": 10.56, "font_name": "SimSun"}]}]}
    assert matrix.compare_word_metrics(measured, profile)["status"] == "PASS"
    measured["east_asia"]["occurrences"][0]["glyphs"][0]["font_name"] = "MicrosoftYaHei"
    assert matrix.compare_word_metrics(measured, profile)["status"] == "FAIL"


def test_libertine_postscript_alias_is_not_a_calibri_substitution():
    profile = {"rules": {"body": {"font": "Linux Libertine O", "size_pt": 9}}}
    measured = {"occurrences": [{"glyphs": [{"font_name": "ABCDEF+LinLibertineO", "size_pt": 9}]}]}
    assert matrix.compare_word_metrics(measured, profile)["status"] == "PASS"
    measured["occurrences"][0]["glyphs"][0]["font_name"] = "Calibri"
    assert matrix.compare_word_metrics(measured, profile)["status"] == "FAIL"


def test_matrix_records_every_selected_id_even_when_one_fails(tmp_path, monkeypatch):
    monkeypatch.setattr("manuweave.presets.list_presets", lambda: [{"id": "ok"}, {"id": "broken"}])

    def load(name):
        if name == "broken":
            raise ValueError("Template asset hash mismatch")
        return {"id": name}

    monkeypatch.setattr("manuweave.presets.load_preset", load)
    monkeypatch.setattr(matrix, "_run_profile", lambda profile, output: {"id": profile["id"], "execution_status": "PASS"})
    output = tmp_path / "matrix"
    report = matrix.run_matrix(output)
    assert report["tested_ids"] == ["ok", "broken"]
    assert report["untested_ids"] == []
    assert report["summary"] == {"PASS": 1, "FAIL": 1, "UNVERIFIED": 0, "selected": 2, "completed": 2, "pending": 0}
    assert report["results"][1]["issues"][0]["message"] == "Template asset hash mismatch"
    assert json.loads((output / "matrix.json").read_text())["status"] == "FAIL"
    assert Path(report["native_tools"]["python"]).is_file()
    with pytest.raises(FileExistsError):
        matrix.run_matrix(output)


def test_merge_preserves_failed_evidence_and_reports_untested_catalog_ids(tmp_path, monkeypatch):
    from manuweave.io import write_json
    monkeypatch.setattr("manuweave.presets.list_presets", lambda: [{"id": "a"}, {"id": "b"}, {"id": "c"}])
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    write_json(old, {"results": [{"id": "a", "execution_status": "FAIL", "compliance_status": "UNVERIFIED"},
                                 {"id": "b", "execution_status": "FAIL", "compliance_status": "UNVERIFIED"}]})
    write_json(new, {"results": [{"id": "a", "execution_status": "PASS", "compliance_status": "UNVERIFIED"}]})
    report = matrix.merge_matrices(tmp_path / "merged", [old, new])
    assert report["summary"] == {"PASS": 1, "FAIL": 1, "UNVERIFIED": 1, "catalog": 3, "tested": 2, "untested": 1}
    assert report["untested_ids"] == ["c"]
    assert len(report["results"][0]["run_history"]) == 2
    assert report["results"][1]["execution_status"] == "FAIL"
    assert report["compliance_status"] == "UNVERIFIED"
    assert report["status"] == "FAIL"
