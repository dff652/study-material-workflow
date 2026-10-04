"""Verify the exact bytes and structural print constraints of a rendered packet."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.metadata
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import subprocess
import zipfile

from lxml import etree
import pymupdf as fitz

import workflow_common as common
from packet import asset_records, packet_digest, validate_packet
from print_backend.contracts import ExportError, GENERATOR_VERSION, document_dict
from print_backend.renderer import _footer_status
from print_backend.contracts import snapshot_id


_DEPENDENCIES = ("Pillow", "reportlab", "python-docx", "fonttools", "lxml", "PyMuPDF")
_CODE_FILES = (
    "packet.py",
    "workflow_common.py",
    "print_backend/contracts.py",
    "print_backend/fonts.py",
    "print_backend/math.py",
    "print_backend/rich.py",
    "print_backend/renderer.py",
    "render_packet.py",
    "verify_packet.py",
)
_PACKAGE_FILES_LIMIT = 512 * 1024 * 1024
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_NS = {"w": _W, "m": _M, "wp": _WP}
_IMAGE_FILES = {
    "CJK-Regular.ttf", "CJK-Bold.ttf", "Math.ttf", "cjk-LICENSE.txt", "math-LICENSE.txt",
}


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        common.fail("invalid_arguments", "Command-line arguments do not match the tool contract")


def _invalid(message, code="render_integrity_error"):
    common.fail(code, message)


def _record(path):
    path = Path(path)
    common.assert_no_symlinks(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        _invalid("A manifest path is missing or not a regular file")
    expected_size = path.stat().st_size
    if expected_size > _PACKAGE_FILES_LIMIT:
        _invalid("Package file exceeds the verification size limit")
    raw = path.read_bytes()
    if len(raw) != expected_size:
        _invalid("Package file changed while it was being verified")
    return {"sha256": common.digest(raw), "size": len(raw)}


def _walk(root):
    files = set()
    directories = set()
    total = 0
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in dirs:
            child = current_path / name
            if child.is_symlink() or not child.is_dir():
                _invalid("The package tree contains a symlink or invalid directory")
            directories.add(child.relative_to(root).as_posix())
        for name in names:
            child = current_path / name
            if child.is_symlink() or not child.is_file():
                _invalid("The package tree contains a symlink or non-file entry")
            relative = child.relative_to(root).as_posix()
            if relative == "render-manifest.json":
                continue
            total += child.stat().st_size
            if total > _PACKAGE_FILES_LIMIT:
                _invalid("Package contents exceed the verification size limit")
            files.add(relative)
    return files, directories


def _safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts and path.as_posix() == value


def _check_manifest_files(root, manifest):
    files = manifest["files"]
    if not isinstance(files, dict) or "render-manifest.json" in files:
        _invalid("Manifest files must exclude the manifest itself")
    declared_total = 0
    for record in files.values():
        if not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] < 0:
            _invalid("Manifest file size is invalid")
        declared_total += record["size"]
        if declared_total > _PACKAGE_FILES_LIMIT:
            _invalid("Package contents exceed the verification size limit")
    for relative, expected in files.items():
        if not _safe_relative(relative) or not isinstance(expected, dict) or set(expected) != {"sha256", "size"}:
            _invalid("Manifest file record is invalid")
        digest = expected["sha256"]
        size = expected["size"]
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(char not in "0123456789abcdef" for char in digest) or
                type(size) is not int or size < 0 or size > _PACKAGE_FILES_LIMIT):
            _invalid("Manifest file hash or size is invalid")
        path = root / relative
        if _record(path) != expected:
            _invalid(f"Package file does not match its manifest: {relative}")

    actual_files, actual_dirs = _walk(root)
    if actual_files != set(files):
        _invalid("The package file set differs from the manifest")
    expected_dirs = set()
    for relative in files:
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    if actual_dirs != expected_dirs:
        _invalid("The package directory set differs from its recorded files")


def _validate_recipe(recipe, manifest, packet, root):
    fields = {
        "schema_version", "packet_sha256", "packet_record_sha256", "assets", "fonts", "code_sha256",
        "dependencies", "python_version", "backend_version", "renderer_tools",
    }
    if not isinstance(recipe, dict) or set(recipe) != fields or recipe["schema_version"] != "swf.render-recipe.v1":
        _invalid("Render recipe has an invalid schema")
    recipe_sha = common.digest(common.canonical(recipe))
    if manifest["recipe_sha256"] != recipe_sha:
        _invalid("Recipe digest does not match the manifest")
    if (recipe["packet_sha256"] != manifest["packet_sha256"] or
            recipe["packet_sha256"] != packet_digest(packet)):
        _invalid("Packet digest does not match the render recipe")
    packet_record_sha256 = common.digest(common.canonical(packet))
    if recipe["packet_record_sha256"] != packet_record_sha256:
        _invalid("Complete packet record does not match the render recipe")
    if recipe["backend_version"] != GENERATOR_VERSION or recipe["python_version"] != platform.python_version():
        _invalid("The packet was produced by a different renderer or Python version")

    code_files = set(_CODE_FILES)
    if not isinstance(recipe["code_sha256"], dict) or set(recipe["code_sha256"]) != code_files:
        _invalid("Recipe code records are incomplete")
    for relative, expected in recipe["code_sha256"].items():
        current = _record(Path(__file__).resolve().parent / relative)["sha256"]
        if expected != current:
            _invalid("Renderer or helper code changed since this package was created")

    versions = {}
    try:
        for name in _DEPENDENCIES:
            versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise common.WorkflowError("missing_dependency", "A required renderer dependency is missing") from exc
    if recipe["dependencies"] != versions:
        _invalid("Renderer dependency versions changed since this package was created")
    if recipe["renderer_tools"] != {"pdftoppm": _pdftoppm_version()}:
        _invalid("Renderer system tools changed since this package was created")

    expected_assets = asset_records(packet, root / "assets") if _packet_has_assets(packet) else {}
    if any(PurePosixPath(key).as_posix() != key or "\\" in key for key in expected_assets):
        _invalid("Packet asset keys must use normalized relative paths")
    if recipe["assets"] != expected_assets:
        _invalid("Copied packet assets do not match the packet source hashes")
    fonts = recipe["fonts"]
    if not isinstance(fonts, dict) or set(fonts) != {"face_index", "sources", "licenses"}:
        _invalid("Font recipe is invalid")
    if type(fonts["face_index"]) is not int or fonts["face_index"] < 0:
        _invalid("Font face index is invalid")
    if not isinstance(fonts["sources"], dict) or set(fonts["sources"]) != {"regular", "bold", "math"}:
        _invalid("Font source records are incomplete")
    if not isinstance(fonts["licenses"], dict) or set(fonts["licenses"]) != {"cjk", "math"}:
        _invalid("Font license records are incomplete")
    for records in (fonts["sources"], fonts["licenses"]):
        for record in records.values():
            if (not isinstance(record, dict) or set(record) != {"sha256", "size"} or
                    not isinstance(record["sha256"], str) or len(record["sha256"]) != 64 or
                    any(char not in "0123456789abcdef" for char in record["sha256"]) or
                    type(record["size"]) is not int or record["size"] <= 0):
                _invalid("Font source or license record is invalid")

    font_manifest = common.read_json(root / "fonts" / "manifest.json")
    if (not isinstance(font_manifest, dict) or
            font_manifest.get("cjk_face_index") != fonts["face_index"] or
            font_manifest.get("source_hashes") != {role: record["sha256"] for role, record in fonts["sources"].items()} or
            not isinstance(font_manifest.get("files"), dict) or set(font_manifest["files"]) != _IMAGE_FILES):
        _invalid("Generated font manifest does not match the render recipe")
    for name, expected in font_manifest["files"].items():
        if _record(root / "fonts" / name)["sha256"] != expected:
            _invalid("Generated font or copied license does not match its font manifest")
    for role in ("cjk", "math"):
        name = "cjk-LICENSE.txt" if role == "cjk" else "math-LICENSE.txt"
        if _record(root / "fonts" / name) != fonts["licenses"][role]:
            _invalid("Copied font license does not match the recipe")
    return recipe_sha


def _packet_has_assets(packet):
    return any(
        block["kind"] in {"diagram", "formula_image"}
        for document in packet["documents"]
        for page in document["pages"]
        for block in page
    )


def _pdftoppm_version():
    executable = shutil.which("pdftoppm")
    if executable is None:
        return None
    try:
        result = subprocess.run([executable, "-v"], capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "available-version-unknown"
    output = (result.stderr or result.stdout).strip().splitlines()
    return output[0][:160] if output else "available-version-unknown"


def _expected_image_properties(document_value):
    expected = []
    for page in document_value["pages"]:
        for block in page:
            if block["kind"] in {"diagram", "formula_image"}:
                expected.append((block["content"]["alt"], block["content"]["source_ref"]))
    return expected


def _word_counts(path, document_value, snapshot):
    expected_math = sum(block["kind"] == "math" for page in document_value["pages"] for block in page)
    expected_breaks = len(document_value["pages"]) - 1
    expected_pictures = sum(
        block["kind"] in {"map", "diagram", "formula_image"}
        for page in document_value["pages"] for block in page
    )
    image_properties = _expected_image_properties(document_value)
    status = _document_status(document_value)
    footer_prefix = f"{document_value['title']} | {status} | {snapshot[:12]}"
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or any(not _safe_relative(name) for name in names):
                _invalid("Word archive contains duplicate or unsafe member names")
            if sum(item.file_size for item in infos) > _PACKAGE_FILES_LIMIT:
                _invalid("Word archive exceeds the verification size limit")
            if archive.testzip() is not None:
                _invalid("Word archive CRC check failed")
            if "word/document.xml" not in names or "word/footer1.xml" not in names:
                _invalid("Word package lacks its document or footer XML")
            parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
            xml_roots = {}
            for name in names:
                if name.endswith((".xml", ".rels")):
                    xml_roots[name] = etree.fromstring(archive.read(name), parser)
            root = xml_roots["word/document.xml"]
            footer = xml_roots["word/footer1.xml"]
            equations = len(root.xpath(".//m:oMath", namespaces=_NS))
            page_breaks = len(root.xpath(".//w:br[@w:type='page']", namespaces=_NS))
            pictures = len(root.xpath(".//wp:inline", namespaces=_NS))
            if equations != expected_math or page_breaks != expected_breaks or pictures != expected_pictures:
                _invalid("Word equations, explicit page breaks, or pictures do not match the packet")
            props = []
            for item in root.xpath(".//wp:docPr", namespaces=_NS):
                props.append((item.get("descr", ""), item.get("title", "")))
            actual_props = Counter(props)
            expected_props = Counter(image_properties)
            if any(actual_props[key] < amount for key, amount in expected_props.items()):
                _invalid("Word image alternative text or source properties are missing")
            footer_text = " ".join(footer.xpath(".//w:t/text()", namespaces=_NS))
            field_instructions = [value.strip().upper() for value in footer.xpath(".//w:fldSimple/@w:instr", namespaces=_NS)]
            if footer_prefix not in footer_text or not {"PAGE", "NUMPAGES"} <= set(field_instructions):
                _invalid("Word footer does not preserve the source status and page fields")
            for name, root_node in xml_roots.items():
                if name.endswith(".rels") and root_node.xpath(".//*[@TargetMode='External']"):
                    _invalid("Word package must not contain external relationships")
    except common.WorkflowError:
        raise
    except (OSError, zipfile.BadZipFile, etree.XMLSyntaxError, KeyError, ValueError) as exc:
        raise common.WorkflowError("render_integrity_error", "Word package structure could not be verified") from exc
    return {"word_equations": equations, "word_page_breaks": page_breaks, "word_pictures": pictures}


def _document_status(document_value):
    state = document_value["source"]["state"]
    return "历史未审核" if state == "legacy_unreviewed" else state


def _pdf_report(path, document, descriptor, preview_paths):
    document_value = document_dict(document)
    snapshot = snapshot_id(document)
    expected_pages = len(document.pages)
    if descriptor["pages"] != expected_pages:
        _invalid("Manifest page count differs from the packet")
    if len(preview_paths) != expected_pages:
        _invalid("Every PDF page must have exactly one preview")
    status = _footer_status(document)
    pages = 0
    try:
        with fitz.open(path) as pdf:
            if pdf.page_count != expected_pages:
                _invalid("PDF page count differs from its packet")
            for index, page in enumerate(pdf, 1):
                rect = page.rect
                if abs(rect.width - 595.276) > 2 or abs(rect.height - 841.89) > 2:
                    _invalid("PDF page size is not A4")
                text = page.get_text()
                if "\ufffd" in text:
                    _invalid("PDF text contains a missing-glyph replacement character")
                normalized = " ".join(text.split())
                footer = f"{status} | {snapshot[:12]} | {index}/{expected_pages}"
                if footer not in normalized:
                    _invalid("PDF footer does not match source status, snapshot and page count")
                structure = page.get_text("dict")
                for block in structure.get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            x0, y0, x1, y1 = span["bbox"]
                            if x0 < -1.5 or y0 < -1.5 or x1 > rect.width + 1.5 or y1 > rect.height + 1.5:
                                _invalid("PDF text lies outside its page bounds")
                expected_preview = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
                if Path(preview_paths[index - 1]).read_bytes() != expected_preview:
                    _invalid("Page preview does not match its corresponding PDF page")
                pages += 1
    except common.WorkflowError:
        raise
    except Exception as exc:
        raise common.WorkflowError("render_integrity_error", "PDF structure could not be verified") from exc
    return pages, snapshot, document_value


def _verify_package(version_dir, expected_directory_name=None):
    root = Path(os.path.abspath(version_dir))
    common.assert_no_symlinks(root)
    if root.is_symlink() or not root.is_dir():
        _invalid("Version path must be a real directory")
    manifest = common.read_json(root / "render-manifest.json")
    if (not isinstance(manifest, dict) or set(manifest) != {
            "schema_version", "packet_sha256", "recipe_sha256", "recipe", "documents", "files"} or
            manifest["schema_version"] != "swf.render.v1"):
        _invalid("Render manifest has an invalid schema")
    packet = common.read_json(root / "packet.json")
    packet_documents = validate_packet(packet)
    if (manifest["packet_sha256"] != packet_digest(packet) or
            not isinstance(manifest["packet_sha256"], str) or len(manifest["packet_sha256"]) != 64):
        _invalid("Packet content does not match its manifest digest")
    recipe_name = manifest["recipe_sha256"][:24] if isinstance(manifest["recipe_sha256"], str) else ""
    expected_name = expected_directory_name or root.name
    if recipe_name != expected_name:
        _invalid("Version directory name does not match the recipe digest")
    _check_manifest_files(root, manifest)
    _validate_recipe(manifest["recipe"], manifest, packet, root)

    descriptors = manifest["documents"]
    if not isinstance(descriptors, list) or len(descriptors) != len(packet_documents):
        _invalid("Manifest document list differs from the packet")
    total_pages = 0
    for document, descriptor in zip(packet_documents, descriptors):
        expected_fields = {"document_id", "purpose", "pdf", "docx", "pages", "previews"}
        if not isinstance(descriptor, dict) or set(descriptor) != expected_fields:
            _invalid("Document manifest entry has an invalid field set")
        expected_pdf = f"documents/{document.document_id}/document.pdf"
        expected_docx = f"documents/{document.document_id}/document.docx"
        expected_previews = [f"previews/{document.document_id}-{index:03d}.png" for index in range(1, len(document.pages) + 1)]
        if (descriptor["document_id"] != document.document_id or descriptor["purpose"] != document.purpose or
                descriptor["pdf"] != expected_pdf or descriptor["docx"] != expected_docx or
                descriptor["previews"] != expected_previews):
            _invalid("Document manifest paths or identity differ from the packet")
        if any(not _safe_relative(value) for value in (descriptor["pdf"], descriptor["docx"], *descriptor["previews"])):
            _invalid("Document manifest contains an unsafe path")
        pdf_path = root / descriptor["pdf"]
        preview_paths = [root / preview for preview in descriptor["previews"]]
        page_count, snapshot, value = _pdf_report(pdf_path, document, descriptor, preview_paths)
        total_pages += page_count
        word_path = root / descriptor["docx"]
        _word_counts(word_path, value, snapshot)
    report = {
        "status": "passed",
        "packet_sha256": manifest["packet_sha256"],
        "recipe_sha256": manifest["recipe_sha256"],
        "documents": len(packet_documents),
        "pdf_pages": total_pages,
        "human_review": "not_tested",
        "word_client": "not_tested",
    }
    return report, manifest


def verify_packet(version_dir) -> dict:
    """Verify package bytes and machine-readable document structure only."""
    try:
        report, _ = _verify_package(version_dir)
        return report
    except common.WorkflowError:
        raise
    except ExportError as exc:
        raise common.WorkflowError(exc.code, str(exc)) from exc
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise common.WorkflowError("render_integrity_error", "Packet package could not be verified") from exc


def _main(argv=None):
    def run():
        parser = _JsonArgumentParser(description=__doc__)
        parser.add_argument("version_dir")
        args = parser.parse_args(argv)
        return verify_packet(args.version_dir)
    return common.cli_result(run)


if __name__ == "__main__":
    raise SystemExit(_main())
