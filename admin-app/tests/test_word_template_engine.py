"""Unit tests for Word template tag replacement."""
from __future__ import annotations

import io
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.word_template_engine import (
    SUPPORTED_TAG_NAMES,
    _replace_tags_in_xml,
    fill_word_template_bytes,
    find_unfilled_tags,
    scan_template_tags,
)

_MAPPING = {
    "{{NOMBRE}}": "Juan Pérez",
    "{{DNI}}": "12345678",
    "{{DEUDA}}": "1,500.00",
}


def _minimal_docx_xml(body_inner: str, part: str = "document") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body_inner}</w:body></w:document>"
    ).replace("w:document", f"w:{part}")


def _wp(*runs: str) -> str:
    parts = []
    for text in runs:
        parts.append(f"<w:r><w:t>{text}</w:t></w:r>")
    return f"<w:p>{''.join(parts)}</w:p>"


def _wp_with_styles(*runs: tuple[str, bool]) -> str:
    parts = []
    for text, bold in runs:
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        parts.append(f"<w:r>{rpr}<w:t>{text}</w:t></w:r>")
    return f"<w:p><w:pPr><w:jc w:val=\"left\"/></w:pPr>{''.join(parts)}</w:p>"


def _build_docx(parts: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        for name, xml in parts.items():
            zf.writestr(name, xml.encode("utf-8"))
    return buf.getvalue()


def test_single_run_replacement():
    xml = _minimal_docx_xml(_wp("Cliente: {{NOMBRE}}"))
    result = _replace_tags_in_xml(xml, _MAPPING)
    assert "Juan Pérez" in result
    assert "{{NOMBRE}}" not in result


def test_split_tag_replacement():
    xml = _minimal_docx_xml(_wp("{{NOM", "BRE}}"))
    result = _replace_tags_in_xml(xml, _MAPPING)
    assert "Juan Pérez" in result
    assert "{{NOM" not in result
    assert "BRE}}" not in result


def test_three_part_split_tag():
    xml = _minimal_docx_xml(_wp("{{", "NOMBRE", "}}"))
    result = _replace_tags_in_xml(xml, _MAPPING)
    assert "Juan Pérez" in result
    assert "{{" not in result or "NOMBRE" not in result


def test_header_part():
    header_xml = _minimal_docx_xml(_wp("{{DNI}}"), part="hdr")
    result = _replace_tags_in_xml(header_xml, _MAPPING)
    assert "12345678" in result
    assert "{{DNI}}" not in result


def test_split_tag_realistic_multi_run():
    xml = _minimal_docx_xml(
        _wp_with_styles(("Señor(a): {{NOM", True), ("BRE}}", False))
    )
    result = _replace_tags_in_xml(xml, _MAPPING)
    assert "Juan Pérez" in result
    ET.fromstring(result.encode("utf-8"))


def test_fill_word_template_bytes_end_to_end():
    docx_bytes = _build_docx({
        "word/document.xml": _minimal_docx_xml(_wp("{{NOM", "BRE}} — S/ {{DEUDA}}")),
    })
    filled = fill_word_template_bytes(docx_bytes, _MAPPING)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(filled)
        tmp_path = tmp.name
    try:
        unfilled = find_unfilled_tags(tmp_path)
        assert not unfilled, f"Expected no unfilled tags, got: {unfilled}"
    finally:
        os.unlink(tmp_path)


def test_docx_zip_entry_sizes_match_content():
    docx_bytes = _build_docx({
        "word/document.xml": _minimal_docx_xml(_wp("{{NOM", "BRE}}")),
    })
    filled = fill_word_template_bytes(docx_bytes, _MAPPING)
    with zipfile.ZipFile(io.BytesIO(filled), "r") as zf:
        for info in zf.infolist():
            data = zf.read(info.filename)
            assert info.file_size == len(data), info.filename


def test_docx_xml_well_formed():
    docx_bytes = _build_docx({
        "word/document.xml": _minimal_docx_xml(_wp("{{NOM", "BRE}} — {{DEUDA}}")),
    })
    filled = fill_word_template_bytes(docx_bytes, _MAPPING)
    with zipfile.ZipFile(io.BytesIO(filled), "r") as zf:
        xml_text = zf.read("word/document.xml").decode("utf-8")
    ET.fromstring(xml_text.encode("utf-8"))


def test_openable_by_zipfile():
    docx_bytes = _build_docx({
        "word/document.xml": _minimal_docx_xml(_wp("{{NOMBRE}}", " — S/ {{DEUDA}}")),
    })
    filled = fill_word_template_bytes(docx_bytes, _MAPPING)
    with zipfile.ZipFile(io.BytesIO(filled), "r") as zf:
        assert zf.testzip() is None


def test_unknown_tag_detected_in_scan():
    docx_bytes = _build_docx({
        "word/document.xml": _minimal_docx_xml(_wp("{{NOMBRE}} {{TELEFONO}}")),
    })
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp.write(docx_bytes)
        tmp_path = tmp.name
    try:
        scan = scan_template_tags(tmp_path)
        assert "NOMBRE" in scan["supported"]
        assert "TELEFONO" in scan["unknown"]
        assert scan["has_issues"] is True
    finally:
        os.unlink(tmp_path)


def test_supported_tag_names_match_template_engine():
    from services.template_engine import TAGS

    assert SUPPORTED_TAG_NAMES == frozenset(TAGS.keys())


if __name__ == "__main__":
    tests = [
        test_single_run_replacement,
        test_split_tag_replacement,
        test_three_part_split_tag,
        test_header_part,
        test_split_tag_realistic_multi_run,
        test_fill_word_template_bytes_end_to_end,
        test_docx_zip_entry_sizes_match_content,
        test_docx_xml_well_formed,
        test_openable_by_zipfile,
        test_unknown_tag_detected_in_scan,
        test_supported_tag_names_match_template_engine,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  [PASS] {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {fn.__name__}: {e}")
    if failed:
        sys.exit(1)
    print(f"All {len(tests)} tests passed.")
