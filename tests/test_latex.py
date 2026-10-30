import pytest

from manuweave.latex import apply_latex, audit_latex, compile_latex, inspect_latex, learn_latex_style


@pytest.fixture
def project(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.tex").write_text("\\documentclass{article}\n\\newcommand{\\val}{42}\n\\begin{document}\n\\section{Methods}\n\\input{parts/method}\n\\bibliography{refs}\n\\end{document}\n")
    (source / "parts").mkdir()
    (source / "parts/method.tex").write_text("Observed value 42.\n\\begin{equation}E=mc^2\\end{equation}\n")
    (source / "refs.bib").write_text("@article{real,title={Synthetic fixture},year={2024}}")
    return source


def test_native_multifile_two_presets(project, tmp_path):
    profile = {"id": "one", "page": {"columns": 1, "margin_left_mm": 25, "width_mm": 210, "height_mm": 297}, "latex": {"documentclass": "article", "options": ["11pt"]}}
    output = tmp_path / "one"
    result = apply_latex(project, output, profile)
    assert result["audit"]["content"] == "PASS"
    assert result["audit"]["style"] == "PASS"
    assert "paperwidth=210mm,paperheight=297mm" in (output / "manuweave-layout.tex").read_text()
    assert (output / "parts/method.tex").read_bytes() == (project / "parts/method.tex").read_bytes()
    profile["page"]["columns"] = 2
    second = tmp_path / "two"
    apply_latex(output, second, profile)
    assert "twocolumn" in (second / "main.tex").read_text()
    assert audit_latex(project, second, profile)["content"] == "PASS"
    third = tmp_path / "three"
    apply_latex(second, third, profile)
    assert (second / "main.tex").read_bytes() == (third / "main.tex").read_bytes()


@pytest.mark.parametrize("replacement", ["Observed value 43.", "\\begin{equation}E=mc^3\\end{equation}"])
def test_modified_data_or_equation_detected(project, tmp_path, replacement):
    out = tmp_path / "formatted"
    apply_latex(project, out, {})
    (out / "parts/method.tex").write_text(replacement)
    assert audit_latex(project, out)["content"] == "FAIL"


@pytest.mark.parametrize("unsafe", [r"\input{../../private}", r"\write18{touch bad}", r"\directlua{os.execute('bad')}", r"\input{C:/secret}", r"^^5cwrite18"])
def test_unsafe_project_rejected(project, tmp_path, unsafe):
    with (project / "parts/method.tex").open("a") as file:
        file.write(unsafe)
    assert inspect_latex(project)["risks"]
    with pytest.raises(ValueError, match="Unsafe"):
        apply_latex(project, tmp_path / "out", {})
    assert compile_latex(project, tmp_path / "render")["status"] == "FAIL"


def test_missing_existing_local_tool_is_unverified(project, tmp_path, monkeypatch):
    monkeypatch.setattr("manuweave.latex.shutil.which", lambda _: None)
    result = compile_latex(project, tmp_path / "render")
    assert result["status"] == "UNVERIFIED"
    assert not (tmp_path / "render").exists()


def test_native_preflight_rejects_dynamic_file_primitives(project, tmp_path, monkeypatch):
    monkeypatch.setattr("manuweave.latex._run_native_tex", lambda *_: pytest.fail("Unsafe source must not start any process"))
    with (project / "parts/method.tex").open("a") as file:
        file.write(r"\pdffiledump{C:/private/data}")
    result = compile_latex(project, tmp_path / "render")
    assert result["status"] == "FAIL"
    assert result["isolation"] == "none"
    assert not (tmp_path / "render").exists()


def test_native_compile_copies_project_and_disables_shell_escape(project, tmp_path, monkeypatch):
    original = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    monkeypatch.setattr("manuweave.latex.shutil.which", lambda name: "/existing/" + name)
    calls = []

    def execute(command, directory, environment, timeout):
        assert directory != project and project not in directory.parents
        assert "-norc" in command and "-no-shell-escape" in command
        assert environment["openin_any"] == "p" and environment["openout_any"] == "p"
        assert 0 < timeout <= 90
        assert (directory / "parts/method.tex").read_bytes() == original[next(key for key in original if key.name == "method.tex")]
        (directory / "parts/method.tex").write_text("Changes in the temporary copy only.")
        build = directory / "manuweave-build"
        (build / "main.pdf").write_bytes(b"%PDF-native-boundary-fixture")
        (build / "main.log").write_text("Final native log with no diagnostics.")
        calls.append(directory)
        return 0, "Native process boundary test", False

    monkeypatch.setattr("manuweave.latex._run_native_tex", execute)
    result = compile_latex(project, tmp_path / "render")
    assert result["status"] == "PASS"
    assert result["security"] == "native_no_shell_escape_strict_preflight" and result["isolation"] == "none"
    assert all(not directory.exists() for directory in calls)
    assert original == {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}


def test_compile_settings_do_not_accept_image(project, tmp_path):
    import json
    (project / "manuweave-compile.json").write_text(json.dumps({"format": "manuweave-compile-v1", "engine": "auto", "image": "legacy"}))
    with pytest.raises(ValueError, match="Unrecognized native compilation settings"):
        compile_latex(project, tmp_path / "render")


def test_native_timeout_terminates_owned_process(project):
    import os
    import sys
    from manuweave.latex import _run_native_tex

    code, output, timed_out = _run_native_tex([sys.executable, "-c", "import time; time.sleep(10)"], project, os.environ.copy(), .1)
    assert timed_out and code != 0
    assert "resource deadline" in output


def test_missing_main_and_unsafe_profile(project, tmp_path):
    with pytest.raises(ValueError):
        apply_latex(project, tmp_path / "out", {"latex": {"documentclass": r"article}\input{x"}})
    assert not (tmp_path / "out").exists()
    with pytest.raises(ValueError):
        apply_latex(project, project / "out", {})


def test_never_overwrite(project):
    with pytest.raises(FileExistsError):
        apply_latex(project, project, {})


def test_layout_filename_collision_preserved(project, tmp_path):
    (project / "manuweave-layout.tex").write_text("Scientifically meaningful original content.")
    with pytest.raises(ValueError, match="Existing layout"):
        apply_latex(project, tmp_path / "out", {})
    assert (project / "manuweave-layout.tex").read_text() == "Scientifically meaningful original content."


def test_layout_content_injection_detected(project, tmp_path):
    out = tmp_path / "formatted"
    profile = {"page": {"margin_top_mm": 20}}
    apply_latex(project, out, profile)
    with (out / "manuweave-layout.tex").open("a") as file:
        file.write("Invented result: 97 percent.\n")
    assert audit_latex(project, out, profile)["content"] == "FAIL"
    assert audit_latex(project, out, profile)["style"] == "FAIL"


def test_template_package_conflict(project, tmp_path):
    main = project / "main.tex"
    main.write_text(main.read_text().replace("\\begin{document}", "\\usepackage[round]{natbib}\n\\begin{document}"))
    with pytest.raises(ValueError, match="conflict"):
        apply_latex(project, tmp_path / "out", {"latex": {"packages": {"natbib": "square"}}})


def test_commented_class_and_preamble_are_not_executed(project, tmp_path):
    main = project / "main.tex"
    comment = "% \\documentclass{fake} \\begin{document}\n"
    main.write_text(comment + main.read_text())
    output = tmp_path / "formatted"
    apply_latex(project, output, {"latex": {"documentclass": "report"}})
    assert (output / "main.tex").read_text().startswith(comment + "\\documentclass{report}")


def test_full_pipeline_schema_plan_run_resume(project, tmp_path, monkeypatch):
    from manuweave import pipeline
    from manuweave.models import DocumentIR
    from manuweave.presets import load_preset

    monkeypatch.setattr("manuweave.render.render", lambda *_: {"status": "UNVERIFIED", "reason": "No renderer in this contract integration test"})
    ir = DocumentIR.model_validate(pipeline.document_ir(project))
    assert "heading1" in {block.role for block in ir.blocks}
    profile = load_preset("en-article-single")
    edit_plan = pipeline.plan(project, profile)
    assert edit_plan["operations"][-1]["op"] == "format_document"
    result = pipeline.run(project, tmp_path / "run", profile)
    assert result["status"] == "UNVERIFIED"
    assert pipeline.run(state_path=result["state"]) == result


def test_learn_static_latex_reference_with_sources(project, tmp_path):
    from manuweave.models import StyleProfile

    main = project / "main.tex"
    preamble = r"""\documentclass[12pt,twocolumn,a4paper]{article}
\usepackage{graphicx,amsmath}
\usepackage[margin=1in]{geometry}
\input{layout}
\newcommand{\example}{\geometry{left=78mm}}
"""
    main.write_text(main.read_text().replace("\\documentclass{article}\n", preamble))
    (project / "layout.tex").write_text("\\geometry{left=30mm}\n")
    profile = learn_latex_style(project)
    StyleProfile.model_validate(profile)
    assert profile["page"]["margin_left_mm"] == 30
    assert profile["page"]["margin_right_mm"] == 25.4
    assert profile["page"]["columns"] == 2
    assert profile["page"]["width_mm"] == 210
    assert profile["latex"]["packages"] == {"graphicx": "", "amsmath": ""}
    assert profile["evidence"]["page.margin_left_mm"]["source"]["file"] == "layout.tex"
    assert profile["evidence"]["page.margin_left_mm"]["exceptions"][0]["value"] == 25.4
    assert "Observed value" not in str(profile)
    assert apply_latex(project, tmp_path / "formatted", profile)["audit"]["style"] == "PASS"


def test_dynamic_latex_reference_is_not_assumed(project):
    main = project / "main.tex"
    main.write_text(main.read_text().replace("\\begin{document}", "\\newcommand{\\mymargin}{2cm}\n\\geometry{left=\\mymargin}\n\\ifdefined\\custom\n\\geometry{right=20mm}\n\\fi\n\\begin{document}"))
    profile = learn_latex_style(project)
    assert "margin_left_mm" not in profile["page"]
    assert "margin_right_mm" not in profile["page"]
    assert any(issue["status"] == "UNKNOWN" for issue in profile["unknown"])
