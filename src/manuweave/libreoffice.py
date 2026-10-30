"""Optional PDF export through an already installed local LibreOffice."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import signal
import zipfile

PROFILE = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Load"><prop oor:name="UpdateLinksMode" oor:op="fuse"><value>0</value></prop></item>
</oor:items>
'''


def _stop_process_tree(process):
    """Stop only the process group launched for this isolated-profile export."""
    if os.name == "nt":
        taskkill = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe")
        try:
            subprocess.run([taskkill, "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _call(command: list[str], timeout: float = 90):
    kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", **kwargs)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException:
        _stop_process_tree(process)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def available() -> dict:
    explicit = os.environ.get("MANUWEAVE_SOFFICE")
    local = explicit or shutil.which("soffice") or shutil.which("libreoffice")
    if local:
        path = Path(local).expanduser().resolve()
        if path.is_file():
            return {"status": "PASS", "mode": "local", "executable": str(path),
                    "local_soffice": str(path), "renderer": "LibreOffice local"}
        if explicit:
            return {"status": "UNVERIFIED", "mode": "local", "executable": None,
                    "reason": "MANUWEAVE_SOFFICE does not identify an existing executable"}
    return {"status": "UNVERIFIED", "mode": "local", "executable": None,
            "reason": "No installed local LibreOffice executable is available"}


def export_pdf(source: Path, output_dir: Path) -> dict:
    """Export a DOCX without rewriting it or exposing it to any network service."""
    from .word import _package
    from .render import word_render_risk

    source, output_dir = Path(source).resolve(), Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError("LibreOffice output must be a new directory")
    if not source.is_file() or source.suffix.lower() != ".docx":
        raise ValueError("LibreOffice export requires an existing DOCX")
    try:
        _package(source)
        reason = word_render_risk(source)
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        return {"status": "FAIL", "pdf": None, "renderer": "LibreOffice", "log": str(error)}
    if reason:
        return {"status": "FAIL", "pdf": None, "renderer": "LibreOffice", "log": reason}
    backend = available()
    if backend["status"] != "PASS":
        return {**backend, "pdf": None, "renderer": "LibreOffice", "log": backend["reason"]}
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    output_dir.mkdir(parents=True)
    renderer = backend["renderer"]
    try:
        with tempfile.TemporaryDirectory(prefix="manuweave-lo-") as temp:
            temporary = Path(temp)
            staged = temporary / "input.docx"
            shutil.copyfile(source, staged)
            profile = temporary / "profile"
            (profile / "user").mkdir(parents=True)
            (profile / "user" / "registrymodifications.xcu").write_text(PROFILE, encoding="utf-8")
            command = [backend["executable"], "--headless", "--nologo", "--nodefault", "--nolockcheck", "--nofirststartwizard",
                       "-env:UserInstallation=" + profile.as_uri(), "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(output_dir), str(staged)]
            result = _call(command, timeout=90)
            log = result.stdout + result.stderr
            status = "PASS" if result.returncode == 0 and (output_dir / "input.pdf").is_file() else "FAIL"
    except subprocess.TimeoutExpired as error:
        status, log = "FAIL", "LibreOffice export exceeded the 90-second resource deadline: " + str(error)
    except (OSError, ValueError) as error:
        status, log = "FAIL", str(error)
    if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
        status, log = "FAIL", log + "\nOriginal manuscript changed unexpectedly"
    pdf = output_dir / "input.pdf"
    if pdf.is_file():
        with pdf.open("rb") as handle:
            if not handle.read(5).startswith(b"%PDF-"):
                status, log = "FAIL", log + "\nExporter did not produce a PDF"
    (output_dir / "libreoffice.log").write_text(log, encoding="utf-8")
    report = {"status": status, "pdf": str(pdf) if status == "PASS" else None, "renderer": renderer,
              "log": str(output_dir / "libreoffice.log"), "source_sha256": original_hash,
              "mode": "local", "executable": backend["executable"],
              "network": "External document resources rejected; no upload service"}
    (output_dir / "libreoffice.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
