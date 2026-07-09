"""
Word Template Engine
=====================
Fills {{TAG}} placeholders in a .docx template and exports editable/output
documents from the same source template.

Conversion pipeline:
  .docx (template) → fill tags → .docx (filled) → PDF → JPG page(s)

PDF conversion (in priority order):
  1. docx2pdf  — MS Word COM automation (Windows, best quality)
  2. LibreOffice subprocess — if soffice/libreoffice is on PATH

Requires: python-docx, pymupdf
Optional: docx2pdf (pip install docx2pdf)
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.sax.saxutils as saxutils
import zipfile


UNFILLED_TAG_RE = re.compile(r"\{\{[A-Z_]+\}\}")
_TAG_FRAGMENT_RE = re.compile(r"\{\{[A-Z_]*|\}\}|[A-Z_]+\}\}")
_TEMPLATE_TAG_RE = re.compile(r"\{\{([A-Z_]+)\}\}")
_WT_RE = re.compile(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", re.DOTALL)
_WP_BLOCK_RE = re.compile(r"(<w:p\b.*?</w:p>)", re.DOTALL)
_WR_BLOCK_RE = re.compile(r"(<w:r\b.*?</w:r>)", re.DOTALL)
_WP_OPEN_RE = re.compile(r"(<w:p\b[^>]*>)")
_WPPPR_RE = re.compile(r"(<w:pPr\b.*?</w:pPr>)", re.DOTALL)
_WRPR_RE = re.compile(r"(<w:rPr\b.*?</w:rPr>)", re.DOTALL)

SUPPORTED_TAG_NAMES: frozenset[str] = frozenset({
    "NOMBRE", "DNI", "DIRECCION", "CODIGO", "ZONA", "SECCION", "CAMPANA",
    "DEUDA", "CODIGO_PAGO", "FECHA", "FECHA_VENCIMIENTO",
    "GESTOR_NOMBRE", "GESTOR_CELULAR",
})


# ── Build replacement mapping ──────────────────────────────────────

def build_tag_mapping(
    client: dict,
    gestor_config: dict | None = None,
    campaign_info: dict | None = None,
    gestor_name: str = "",
    gestor_phone: str = "",
) -> dict[str, str]:
    """Return a dict mapping '{{TAG}}' → resolved value for the given client."""
    gc = dict(gestor_config or {})
    if gestor_name:
        gc.setdefault("nombre_gestor", gestor_name)
    if gestor_phone:
        gc.setdefault("telefono_gestor", gestor_phone)
    ci = campaign_info or {}

    from .template_engine import _es_date

    nombre = (
        client.get("nombre_completo", "").strip()
        or (
            f"{client.get('nombres', '')} "
            f"{client.get('apellido_paterno', '')} "
            f"{client.get('apellido_materno', '')}".strip()
        )
    )
    dni = str(client.get("numero_documento", client.get("dni", "")))

    addr_parts = [
        client.get("direccion", ""),
        client.get("distrito", ""),
        client.get("provincia", ""),
    ]
    direccion = ", ".join(p for p in addr_parts if p) or client.get("direccion", "")

    deuda_raw = client.get(
        "importe_deuda_pendiente",
        client.get("importe_deuda_asignada", client.get("saldo", 0)),
    )
    try:
        deuda_str = f"{float(deuda_raw):,.2f}"
    except (ValueError, TypeError):
        deuda_str = "0.00"

    values: dict[str, str] = {
        "NOMBRE":            nombre,
        "DNI":               dni,
        "DIRECCION":         direccion,
        "CODIGO":            str(client.get("codigo_cliente", "")),
        "ZONA":              str(client.get("zona", "")),
        "SECCION":           str(client.get("seccion", "")),
        "CAMPANA":           str(ci.get("nombre", client.get("campana", ""))),
        "DEUDA":             deuda_str,
        "CODIGO_PAGO":       str(client.get("codigo_cliente", client.get("codigo_pago", ""))),
        "FECHA":             _es_date(),
        "FECHA_VENCIMIENTO": str(client.get("fecha_vencimiento", "—")),
        "GESTOR_NOMBRE":     gc.get("nombre_gestor", ""),
        "GESTOR_CELULAR":    gc.get("telefono_gestor", ""),
    }

    return {f"{{{{{k}}}}}": v for k, v in values.items()}


def _should_process_zip_member(name: str) -> bool:
    """True for Word XML parts that may contain {{TAG}} placeholders."""
    if not name.startswith("word/") or not name.endswith(".xml"):
        return False
    if "/_rels/" in name:
        return False
    base = os.path.basename(name)
    if base.startswith("settings") or base.startswith("styles") or base.startswith("theme"):
        return False
    return True


def _paragraph_needs_tag_processing(combined: str, mapping: dict[str, str]) -> bool:
    """True when paragraph text may still contain placeholders."""
    if UNFILLED_TAG_RE.search(combined):
        return True
    if "{{" in combined or "}}" in combined:
        return True
    return any(tag in combined for tag in mapping)


def _collect_tag_issues_from_text(text: str) -> tuple[set[str], set[str]]:
    """Return (complete_unfilled_tags, fragment_markers) from plain text."""
    complete = set(UNFILLED_TAG_RE.findall(text))
    fragments: set[str] = set()
    if "{{" in text or "}}" in text:
        for match in _TAG_FRAGMENT_RE.finditer(text):
            fragment = match.group(0)
            if fragment not in complete and not any(
                tag.startswith(fragment) or tag.endswith(fragment)
                for tag in complete
            ):
                fragments.add(fragment)
    return complete, fragments


def _collect_tag_issues_from_xml(xml_text: str) -> tuple[set[str], set[str]]:
    """Return (complete_unfilled_tags, fragment_markers) from XML text."""
    complete = set(UNFILLED_TAG_RE.findall(xml_text))
    fragments: set[str] = set()
    for match in _WT_RE.finditer(xml_text):
        text = saxutils.unescape(match.group(2))
        part_complete, part_frags = _collect_tag_issues_from_text(text)
        complete.update(part_complete)
        fragments.update(part_frags)
    return complete, fragments


def _apply_mapping_to_text(text: str, mapping: dict[str, str]) -> str:
    result = text
    for tag, value in mapping.items():
        result = result.replace(tag, str(value or ""))
    return result


def _replace_split_tags_in_wp_block(block: str, mapping: dict[str, str]) -> str:
    """
    Merge w:t text inside a paragraph, replace tags, rebuild the paragraph safely.

    Reconstructs a single w:r with the replaced text instead of mutating indices
    on a modified string (which corrupts XML when Word split tags across runs).
    """
    wt_matches = list(_WT_RE.finditer(block))
    if not wt_matches:
        return block

    combined = "".join(saxutils.unescape(m.group(2)) for m in wt_matches)
    if not _paragraph_needs_tag_processing(combined, mapping):
        return block

    replaced = _apply_mapping_to_text(combined, mapping)
    if replaced == combined:
        return block

    escaped = saxutils.escape(replaced)
    preserve = (
        replaced.startswith(" ")
        or replaced.endswith(" ")
        or "  " in replaced
        or "\t" in replaced
    )
    t_attr = ' xml:space="preserve"' if preserve else ""

    open_match = _WP_OPEN_RE.search(block)
    if not open_match:
        return block
    p_open = open_match.group(1)

    ppr_match = _WPPPR_RE.search(block)
    ppr = ppr_match.group(1) if ppr_match else ""

    wr_matches = list(_WR_BLOCK_RE.finditer(block))
    if not wr_matches:
        return block
    first_wr = wr_matches[0].group(1)
    rpr_match = _WRPR_RE.search(first_wr)
    rpr = rpr_match.group(1) if rpr_match else ""

    new_run = f"<w:r>{rpr}<w:t{t_attr}>{escaped}</w:t></w:r>"
    return f"{p_open}{ppr}{new_run}</w:p>"


def _replace_tags_in_xml(xml_text: str, mapping: dict[str, str]) -> str:
    """Replace {{TAG}} across full XML, then merge/replace split tags per paragraph."""
    result = _apply_mapping_to_text(xml_text, mapping)

    def _process_paragraph(match: re.Match[str]) -> str:
        block = match.group(1)
        wt_matches = list(_WT_RE.finditer(block))
        if not wt_matches:
            return block
        combined = "".join(saxutils.unescape(m.group(2)) for m in wt_matches)
        if not _paragraph_needs_tag_processing(combined, mapping):
            return block
        return _replace_split_tags_in_wp_block(block, mapping)

    return _WP_BLOCK_RE.sub(_process_paragraph, result)


def _repack_docx_zip(entries: list[tuple[str, bytes, int]]) -> bytes:
    """Write a new .docx ZIP with fresh entry metadata (CRC/size)."""
    out_buf = io.BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for filename, data, compress_type in entries:
            ct = (
                compress_type
                if compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                else zipfile.ZIP_DEFLATED
            )
            zout.writestr(filename, data, compress_type=ct)
    return out_buf.getvalue()


def _iter_docx_xml_texts(docx_source: str | bytes) -> list[tuple[str, str]]:
    """Read processable word/*.xml parts from a .docx path or bytes."""
    texts: list[tuple[str, str]] = []
    if isinstance(docx_source, bytes):
        zf_ctx = zipfile.ZipFile(io.BytesIO(docx_source), "r")
    else:
        zf_ctx = zipfile.ZipFile(docx_source, "r")
    with zf_ctx as zf:
        for name in zf.namelist():
            if not _should_process_zip_member(name):
                continue
            try:
                xml_text = zf.read(name).decode("utf-8", errors="replace")
            except Exception:
                continue
            texts.append((name, xml_text))
    return texts


def scan_template_tags(docx_path: str) -> dict[str, list[str] | bool]:
    """
    Scan a .docx template for placeholder tags.

    Returns dict with keys:
      supported — recognized {{TAG}} names found
      unknown — {{TAG}} names not in SUPPORTED_TAG_NAMES
      fragments — suspected split/incomplete tag fragments in XML
      has_issues — True if unknown tags or fragments were found
    """
    supported: set[str] = set()
    unknown: set[str] = set()
    fragments: set[str] = set()

    for _name, xml_text in _iter_docx_xml_texts(docx_path):
        for tag_name in _TEMPLATE_TAG_RE.findall(xml_text):
            if tag_name in SUPPORTED_TAG_NAMES:
                supported.add(tag_name)
            else:
                unknown.add(tag_name)
        _complete, frags = _collect_tag_issues_from_xml(xml_text)
        fragments.update(frags)

    return {
        "supported": sorted(supported),
        "unknown": sorted(unknown),
        "fragments": sorted(fragments),
        "has_issues": bool(unknown or fragments),
    }


def fill_word_template_bytes(
    template_bytes: bytes,
    mapping: dict[str, str],
) -> bytes:
    """Fill placeholders inside a .docx byte buffer (ZIP/XML traversal)."""
    in_buf = io.BytesIO(template_bytes)
    entries: list[tuple[str, bytes, int]] = []

    with zipfile.ZipFile(in_buf, "r") as zin:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if _should_process_zip_member(item.filename):
                try:
                    xml_text = data.decode("utf-8")
                except UnicodeDecodeError:
                    xml_text = data.decode("utf-8", errors="replace")
                data = _replace_tags_in_xml(xml_text, mapping).encode("utf-8")
            entries.append((item.filename, data, item.compress_type))

    return _repack_docx_zip(entries)


def find_unfilled_tags(docx_path: str) -> list[str]:
    """Return unique {{TAG}} placeholders still present in a filled .docx."""
    found: set[str] = set()
    fragments: set[str] = set()
    for _name, xml_text in _iter_docx_xml_texts(docx_path):
        complete, frags = _collect_tag_issues_from_xml(xml_text)
        found.update(complete)
        fragments.update(frags)
    issues = sorted(found)
    if fragments:
        issues.extend(f"[fragmento:{f}]" for f in sorted(fragments))
    return issues


def assert_no_unfilled_tags(docx_path: str) -> list[str]:
    """
    Return remaining unfilled tags. Empty list means the document is fully filled.
    """
    return find_unfilled_tags(docx_path)


# ── Fill all placeholders in a document ───────────────────────────

def fill_word_template(
    template_path: str,
    client: dict,
    gestor_config: dict | None = None,
    campaign_info: dict | None = None,
    output_path: str | None = None,
    gestor_name: str = "",
    gestor_phone: str = "",
) -> str:
    """
    Open *template_path*, replace all {{TAG}} placeholders with client data,
    and save to *output_path* (created if None → temporary file).

    Uses ZIP/XML traversal so text boxes, alternate headers/footers and nested
    tables are covered — not only python-docx body paragraphs.

    Returns the path of the saved filled .docx.
    """
    mapping = build_tag_mapping(
        client,
        gestor_config,
        campaign_info,
        gestor_name=gestor_name,
        gestor_phone=gestor_phone,
    )

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".docx")
        os.close(fd)

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(template_path, "rb") as f:
        filled = fill_word_template_bytes(f.read(), mapping)
    with open(output_path, "wb") as f:
        f.write(filled)
    return output_path


# ── DOCX → PDF conversion ──────────────────────────────────────────

def _app_base_dir() -> str:
    """Directory of the admin-app (or PyInstaller extract dir)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resolve_soffice_path() -> str | None:
    """
    Locate LibreOffice ``soffice`` executable.

    Search order:
      1. Bundled portable copy under admin-app/vendor/libreoffice/
      2. PATH (soffice / libreoffice)
      3. Typical Windows install paths
    """
    bundled_root = os.path.join(_app_base_dir(), "vendor", "libreoffice")
    if os.path.isdir(bundled_root):
        for root, _dirs, files in os.walk(bundled_root):
            for name in ("soffice.exe", "soffice.com", "soffice"):
                if name in files:
                    return os.path.join(root, name)

    for cmd in ("soffice", "libreoffice"):
        found = shutil.which(cmd)
        if found:
            return found

    for pattern in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if os.path.isfile(pattern):
            return pattern
    return None


def check_docx_converter_preflight(*, run_conversion_test: bool = False) -> dict[str, str | bool]:
    """
    Report availability of DOCX→PDF converters for UI preflight.

    When *run_conversion_test* is True, creates a minimal DOCX and attempts
    conversion to verify the toolchain end-to-end.

    Returns dict with keys: ok (bool), method (str), detail (str).
    """
    soffice = resolve_soffice_path()
    method = ""
    if soffice:
        method = "LibreOffice"
        base = {"ok": True, "method": method, "detail": soffice}
    else:
        try:
            import docx2pdf  # noqa: F401
            method = "Microsoft Word (docx2pdf)"
            base = {
                "ok": True,
                "method": method,
                "detail": "Requiere MS Word instalado en este equipo.",
            }
        except ImportError:
            return {
                "ok": False,
                "method": "ninguno",
                "detail": (
                    "Instale LibreOffice, coloque una copia portable en "
                    "admin-app/vendor/libreoffice/, o instale Microsoft Word con docx2pdf."
                ),
            }

    if not run_conversion_test:
        return base

    try:
        from docx import Document

        with tempfile.TemporaryDirectory() as tmp_dir:
            docx_path = os.path.join(tmp_dir, "preflight_test.docx")
            pdf_path = os.path.join(tmp_dir, "preflight_test.pdf")
            doc = Document()
            doc.add_paragraph("Prueba de conversión AntCobranzas")
            doc.save(docx_path)
            docx_to_pdf(docx_path, pdf_path)
            if not os.path.isfile(pdf_path):
                raise RuntimeError("No se generó el PDF de prueba.")
        return {
            "ok": True,
            "method": method or base.get("method", ""),
            "detail": f"{base.get('detail', '')} · Conversión de prueba OK".strip(" ·"),
        }
    except Exception as e:
        return {
            "ok": False,
            "method": method or str(base.get("method", "ninguno")),
            "detail": f"Conversor detectado pero falló la prueba: {e}",
        }


def _docx_to_pdf_via_word(docx_path: str, pdf_path: str) -> None:
    """Convert using docx2pdf (requires MS Word on Windows)."""
    try:
        from docx2pdf import convert
    except ImportError:
        raise ImportError(
            "Instale docx2pdf: pip install docx2pdf\n"
            "También requiere Microsoft Word instalado."
        )
    convert(docx_path, pdf_path)


def _docx_to_pdf_via_libreoffice(docx_path: str, pdf_path: str) -> None:
    """Convert using bundled or system LibreOffice."""
    soffice = resolve_soffice_path()
    if not soffice:
        raise RuntimeError(
            "LibreOffice no encontrado. Coloque una copia portable en "
            "admin-app/vendor/libreoffice/ o instálelo en el sistema."
        )

    out_dir = os.path.dirname(os.path.abspath(pdf_path))
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice falló: {result.stderr}")

    # LibreOffice names the output after the input file
    expected = os.path.join(
        out_dir,
        os.path.splitext(os.path.basename(docx_path))[0] + ".pdf",
    )
    if os.path.abspath(expected) != os.path.abspath(pdf_path) and os.path.exists(expected):
        shutil.move(expected, pdf_path)


def docx_to_pdf(docx_path: str, pdf_path: str) -> None:
    """
    Convert *docx_path* to *pdf_path*.

    Prefers bundled/system LibreOffice; falls back to docx2pdf (MS Word).
    Raises RuntimeError if neither converter is available.
    """
    errors: list[str] = []

    if resolve_soffice_path():
        try:
            _docx_to_pdf_via_libreoffice(docx_path, pdf_path)
            return
        except Exception as e:
            errors.append(f"LibreOffice: {e}")

    try:
        _docx_to_pdf_via_word(docx_path, pdf_path)
        return
    except Exception as e:
        errors.append(f"docx2pdf: {e}")

    if not errors:
        errors.append("LibreOffice: no encontrado")

    raise RuntimeError(
        "No se pudo convertir el Word a PDF.\n"
        + "\n".join(errors)
        + "\n\nSolución: instale LibreOffice, coloque una copia portable en "
        "admin-app/vendor/libreoffice/, o use Microsoft Word con docx2pdf."
    )


# ── PDF → JPG page(s) ─────────────────────────────────────────────

def pdf_to_jpgs(pdf_path: str, output_dir: str, dpi: int = 200) -> list[str]:
    """
    Render each page of *pdf_path* to a JPG in *output_dir*.
    Returns a list of created JPG paths (one per page).
    """
    import fitz  # pymupdf

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)

    doc = fitz.open(pdf_path)
    jpg_paths: list[str] = []

    for page_num, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat, alpha=False)
        if len(doc) == 1:
            jpg_path = os.path.join(output_dir, f"{base_name}.jpg")
        else:
            jpg_path = os.path.join(output_dir, f"{base_name}_p{page_num + 1}.jpg")
        pix.save(jpg_path)
        jpg_paths.append(jpg_path)

    doc.close()
    return jpg_paths


# ── High-level convenience functions ──────────────────────────────

def word_template_to_documents(
    template_path: str,
    client: dict,
    output_dir: str,
    base_filename: str,
    gestor_config: dict | None = None,
    campaign_info: dict | None = None,
    formats: list[str] | None = None,
    dpi: int = 200,
    gestor_name: str = "",
    gestor_phone: str = "",
) -> dict[str, str | list[str]]:
    """
    Fill a Word template and export editable/final documents.

    Supported output formats: ``docx``, ``pdf``, ``jpg``.
    Each format is independent; failures appear as ``{fmt}_error`` keys.
    """
    requested = [str(fmt).lower() for fmt in (formats or ["docx", "pdf"])]
    requested = [fmt for fmt in requested if fmt in {"docx", "pdf", "jpg"}]
    if not requested:
        raise ValueError("Debe solicitar al menos un formato DOCX, PDF o JPG.")

    os.makedirs(output_dir, exist_ok=True)
    docx_path = os.path.join(output_dir, f"{base_filename}.docx")
    fill_word_template(
        template_path,
        client,
        gestor_config,
        campaign_info,
        docx_path,
        gestor_name=gestor_name,
        gestor_phone=gestor_phone,
    )

    unfilled = assert_no_unfilled_tags(docx_path)
    if unfilled:
        outputs: dict[str, str | list[str]] = {
            "docx_error": (
                "Etiquetas sin reemplazar: " + ", ".join(unfilled)
            ),
        }
        if os.path.isfile(docx_path):
            os.remove(docx_path)
        return outputs

    outputs: dict[str, str | list[str]] = {}
    if "docx" in requested:
        outputs["docx"] = docx_path

    pdf_path = os.path.join(output_dir, f"{base_filename}.pdf")
    need_pdf = "pdf" in requested or "jpg" in requested
    if need_pdf:
        try:
            docx_to_pdf(docx_path, pdf_path)
            if "pdf" in requested:
                outputs["pdf"] = pdf_path
        except Exception as e:
            outputs["pdf_error"] = str(e)

    if "jpg" in requested:
        if "pdf" in outputs:
            try:
                outputs["jpg"] = pdf_to_jpgs(pdf_path, output_dir, dpi=dpi)
            except Exception as e:
                outputs["jpg_error"] = str(e)
        else:
            outputs["jpg_error"] = str(
                outputs.get("pdf_error")
                or "No se pudo generar PDF intermedio para JPG."
            )

    return outputs


def word_template_to_jpg(
    template_path: str,
    client: dict,
    output_dir: str,
    base_filename: str,
    gestor_config: dict | None = None,
    campaign_info: dict | None = None,
    dpi: int = 200,
) -> list[str]:
    """
    Fill a Word template with client data and return a list of JPG path(s).

    Steps:
      1. Fill {{TAG}} placeholders → .docx
      2. Convert to PDF (Word COM or LibreOffice)
      3. Render each PDF page to JPG in *output_dir*
    """
    result = word_template_to_documents(
        template_path=template_path,
        client=client,
        output_dir=output_dir,
        base_filename=base_filename,
        gestor_config=gestor_config,
        campaign_info=campaign_info,
        formats=["docx", "jpg"],
        dpi=dpi,
    )
    jpg = result.get("jpg")
    if isinstance(jpg, list) and jpg:
        return jpg
    err = result.get("jpg_error") or result.get("pdf_error") or "No se pudo generar JPG."
    raise RuntimeError(str(err))
