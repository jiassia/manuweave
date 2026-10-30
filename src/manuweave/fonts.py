"""Local font availability checks, separate from actual glyph rendering review."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import ctypes
from pathlib import Path


def _normal(name):
    return re.sub(r"[\s_-]", "", name).casefold()


def pdf_font_family(name):
    name = re.sub(r"^[A-Z]{6}\+", "", name or "")
    normalized = _normal(name)
    normalized = re.sub(r"(?:psmt|mt)$", "", normalized)
    normalized = re.sub(r"(?:bolditalic|boldoblique|bold|italic|oblique|regular)$", "", normalized)
    normalized = re.sub(r"ps$", "", normalized)
    aliases = {"宋体": "simsun", "黑体": "simhei", "楷体": "kaiti", "仿宋": "fangsong", "微软雅黑": "microsoftyahei",
               "linlibertineo": "linuxlibertineo", "linbiolinumo": "linuxbiolinumo"}
    for prefix, family in (("linlibertineo", "linuxlibertineo"), ("linbiolinumo", "linuxbiolinumo")):
        for face in ("b", "i", "bi"):
            aliases[prefix + face] = family
    return aliases.get(normalized, normalized)


def audit_rendered_fonts(source, pdf, profile):
    """Sample unique body text in a real PDF to detect silent Word substitution."""
    import pypdfium2 as pdfium
    from pypdfium2 import raw
    from .word import inspect_docx
    ir = inspect_docx(source)
    properties = profile.get("rules", {}).get("body", {})
    blocks = [b for b in ir["blocks"] if b["role"] == "body" and b["text"].strip()]
    checks = []
    with pdfium.PdfDocument(Path(pdf)) as document:
        for key, pattern in (("font", r"[A-Za-z][A-Za-z0-9 ,.:;-]{11,39}"), ("east_asia_font", r"[\u3400-\u9fff]{4,12}")):
            expected = properties.get(key)
            if not expected:
                continue
            selected = None
            for block in blocks:
                match = re.search(pattern, block["text"])
                if match and sum(match.group(0) in b["text"] for b in ir["blocks"]) == 1:
                    selected = (block["id"], match.group(0))
                    break
            if selected is None:
                checks.append({"property": key, "status": "UNVERIFIED", "reason": "No unique body-text sample of this script"})
                continue
            block_id, needle = selected
            observed = []
            for page_index in range(len(document)):
                page = document[page_index]
                textpage = page.get_textpage()
                search = textpage.search(needle, match_case=True)
                match = search.get_next()
                if match:
                    index, count = match
                    # A short contiguous script-specific sample avoids whitespace fonts.
                    for char in range(index, index + min(count, 4)):
                        flags = ctypes.c_int()
                        size = raw.FPDFText_GetFontInfo(textpage.raw, char, None, 0, ctypes.byref(flags))
                        buffer = ctypes.create_string_buffer(size)
                        raw.FPDFText_GetFontInfo(textpage.raw, char, buffer, size, ctypes.byref(flags))
                        observed.append({"font": buffer.value.decode("utf-8", errors="replace"),
                                         "size_pt": raw.FPDFText_GetFontSize(textpage.raw, char), "page": page_index + 1})
                search.close()
                textpage.close()
                page.close()
            status = "UNVERIFIED" if not observed else "PASS" if all(pdf_font_family(o["font"]) == pdf_font_family(expected) for o in observed) else "FAIL"
            checks.append({"property": key, "block_id": block_id, "expected": expected, "actual": observed, "status": status})
    statuses = [item["status"] for item in checks]
    status = "NOT_APPLICABLE" if not checks else "FAIL" if "FAIL" in statuses else "UNVERIFIED" if "UNVERIFIED" in statuses else "PASS"
    return {"status": status, "checks": checks, "scope": "Actual PDF glyph fonts for unique body samples; other roles and script coverage require page review"}


def check_fonts(profile):
    required = sorted({rule[key] for rule in profile.get("rules", {}).values()
                       for key in ("font", "east_asia_font") if rule.get(key)})
    available = set()
    if os.name == "nt":
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
                    index = 0
                    while True:
                        try:
                            name, _, _ = winreg.EnumValue(key, index)
                            index += 1
                            name = re.sub(r"\s*\([^)]*\)\s*$", "", name)
                            available.update(_normal(part) for part in name.split(" & "))
                        except OSError:
                            break
            except OSError:
                pass
    elif shutil.which("fc-list"):
        result = subprocess.run([shutil.which("fc-list"), "--format=%{family}\n"], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            available.update(_normal(part) for line in result.stdout.splitlines() for part in line.split(","))
    if not available:
        return {"status": "UNVERIFIED", "required": required, "reason": "No supported local font inventory"}
    aliases = {"宋体": "simsun", "黑体": "simhei", "楷体": "kaiti", "仿宋": "fangsong", "微软雅黑": "microsoftyahei"}
    missing = [font for font in required if _normal(font) not in available and _normal(aliases.get(font, font)) not in available]
    return {"status": "FAIL" if missing else "PASS", "required": required, "missing": missing,
            "scope": "Local font family availability; per-glyph substitution requires rendered page inspection"}
