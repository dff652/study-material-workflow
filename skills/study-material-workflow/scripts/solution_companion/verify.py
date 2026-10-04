"""Verify companion package bytes and machine-readable PDF/Word structure."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import platform
import re
import zipfile

from lxml import etree
from PIL import Image
import pymupdf as fitz

import workflow_common as common
from collect_sources import verify_sources
from print_backend.contracts import (
    ExportError,
    document_dict,
    snapshot_id,
    resolve_formula_image,
)
from print_backend.math import formula_strings
from print_backend.rich import RichBreak, RichRun, parse_rich
from print_backend.renderer import image_labels
from render_packet import _LICENSE_FILES, _dependency_versions, _file_record, _pdftoppm_version
from print_backend.contracts import GENERATOR_VERSION
import verify_packet as packet_verify

from .model import asset_records, code_records, compile_documents, content_digest, validate_content


_PACKAGE_LIMIT = 512 * 1024 * 1024
_DOCUMENT_FIELDS = {
    "document_id", "title", "purpose", "page_count", "word_equations",
    "delivery_stem", "formats", "question_ids", "page_questions", "previews",
}


def _invalid(message, code="render_integrity_error"):
    common.fail(code, message)


def _safe_relative(value):
    if type(value) is not str or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (not path.is_absolute() and ".." not in path.parts and "." not in path.parts and
            path.as_posix() == value)


def _tree(root):
    files, directories = set(), set()
    total = 0
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        for name in dirs:
            child = here / name
            if child.is_symlink() or not child.is_dir():
                _invalid("Version tree contains a symlink or invalid directory")
            directories.add(child.relative_to(root).as_posix())
        for name in names:
            child = here / name
            if child.is_symlink() or not child.is_file():
                _invalid("Version tree contains a symlink or non-file entry")
            relative = child.relative_to(root).as_posix()
            if relative == "solution-manifest.json":
                continue
            total += child.stat().st_size
            if total > _PACKAGE_LIMIT:
                _invalid("Version contents exceed the verification size limit")
            files.add(relative)
    return files, directories


def _check_files(root, manifest):
    files = manifest["files"]
    if type(files) is not dict or "solution-manifest.json" in files:
        _invalid("Manifest files must map every package member except itself")
    total = 0
    for relative, expected in files.items():
        if not _safe_relative(relative) or type(expected) is not dict or set(expected) != {"sha256", "size"}:
            _invalid("Manifest file record is malformed")
        sha, size = expected["sha256"], expected["size"]
        if (type(sha) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha) or
                type(size) is not int or size < 0 or size > _PACKAGE_LIMIT):
            _invalid("Manifest file hash or size is invalid")
        total += size
        if total > _PACKAGE_LIMIT:
            _invalid("Version contents exceed the verification size limit")
        if _file_record(root / relative) != expected:
            _invalid("Package file does not match its manifest: " + relative)
    actual_files, actual_dirs = _tree(root)
    if actual_files != set(files):
        _invalid("Package file set differs from its manifest")
    expected_dirs = set()
    for relative in files:
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    if actual_dirs != expected_dirs:
        _invalid("Package directory set differs from its manifest")


def _expected_chunks(blocks, *, include_map=True):
    chunks = []
    for block in blocks:
        kind, content = block.kind, block.content
        if kind in {"title", "sub", "h", "p", "small", "key", "warn", "bridge", "erratum"}:
            chunks.append(_visible_rich_text(content))
        elif kind == "table":
            chunks.extend(_visible_rich_text(cell) for row in content[0] for cell in row)
        elif kind == "math":
            chunks.extend(formula_strings(content))
        elif kind == "map" and include_map:
            chunks.extend(content["root"])
            for group in content["groups"]:
                chunks.extend(group["label"])
                chunks.extend(group["detail"])
        elif kind in {"diagram", "formula_image"}:
            chunks.extend((_visible_rich_text(content["alt"]), _visible_rich_text(content["source_ref"])))
    return [chunk for chunk in chunks if chunk]


def _visible_rich_text(value):
    return "".join("\n" if isinstance(event, RichBreak) else event.text for event in parse_rich(value))


def _expected_map_chunks(blocks):
    chunks = []
    for block in blocks:
        if block.kind != "map":
            continue
        chunks.extend(block.content["root"])
        for group in block.content["groups"]:
            chunks.extend(group["label"])
            chunks.extend(group["detail"])
    return chunks


def _normalize(value):
    return "".join(value.split())


def _check_chunks(actual, expected, *, ordered=True):
    actual = _normalize(actual)
    expected = [_normalize(value) for value in expected]
    expected = [value for value in expected if value]
    if ordered:
        cursor = 0
        for value in expected:
            found = actual.find(value, cursor)
            if found < 0:
                _invalid("Rendered text omits or reorders explicit document content")
            cursor = found + len(value)
    else:
        for value in expected:
            if value not in actual:
                _invalid("Rendered text omits explicit document content")


def _check_pdf_text(path, document):
    try:
        with fitz.open(path) as pdf:
            if pdf.page_count != len(document.pages):
                _invalid("PDF actual page count differs from the explicit document pages")
            for page, blocks in zip(pdf, document.pages):
                extracted = page.get_text()
                _check_chunks(extracted, _expected_chunks(blocks, include_map=False), ordered=True)
                _check_chunks(extracted, _expected_map_chunks(blocks), ordered=False)
    except common.WorkflowError:
        raise
    except Exception as exc:
        raise common.WorkflowError("render_integrity_error", "PDF full-text extraction failed") from exc


def _xml_signature(element):
    name = etree.QName(element).localname
    text = element.text if name == "t" else None
    return (name, text, tuple(_xml_signature(child) for child in element))


def _expected_omml(node):
    kind = node[0]
    if kind == "t":
        return [("r", None, (("t", node[1], ()),))]
    if kind == "r":
        return [item for child in node[1:] for item in _expected_omml(child)]
    if kind == "f":
        return [("f", None, (
            ("num", None, tuple(_expected_omml(node[1]))),
            ("den", None, tuple(_expected_omml(node[2]))),
        ))]
    if kind == "u":
        return [("sSup", None, (
            ("e", None, tuple(_expected_omml(node[1]))),
            ("sup", None, tuple(_expected_omml(node[2]))),
        ))]
    if kind == "d":
        return [("sSub", None, (
            ("e", None, tuple(_expected_omml(node[1]))),
            ("sub", None, tuple(_expected_omml(node[2]))),
        ))]
    _invalid("Unsupported AST node reached verification")


def _text_blocks(document):
    for page in document.pages:
        for block in page:
            if block.kind in {"title", "sub", "h", "p", "small", "key", "warn", "bridge", "erratum"}:
                yield block.content
            elif block.kind == "table":
                yield from (cell for row in block.content[0] for cell in row)
            elif block.kind in {"diagram", "formula_image"}:
                label, source_label = image_labels(block.kind)
                yield label + block.content["alt"]
                yield source_label + block.content["source_ref"]


def _check_word(path, document, expected_equations):
    value = document_dict(document)
    snapshot = snapshot_id(document)
    packet_verify._word_counts(path, value, snapshot)
    try:
        with zipfile.ZipFile(path, "r") as archive:
            parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
            root = etree.fromstring(archive.read("word/document.xml"), parser)
            ns = packet_verify._NS
            text_values = root.xpath(".//w:t/text() | .//m:t/text()", namespaces=ns)
            _check_chunks("".join(text_values), _expected_chunks(
                [block for page in document.pages for block in page], include_map=False), ordered=True)

            expected_runs = [
                (event.text, event.superscript)
                for text in _text_blocks(document)
                for event in parse_rich(text)
                if isinstance(event, RichRun)
            ]
            actual_runs = []
            for run in root.xpath(".//w:r[.//w:t]", namespaces=ns):
                run_text = "".join(run.xpath(".//w:t/text()", namespaces=ns))
                properties = run.find("w:rPr", namespaces=ns)
                vertical = None if properties is None else properties.find("w:vertAlign", namespaces=ns)
                actual_runs.append((run_text, vertical is not None and vertical.get(f"{{{ns['w']}}}val") == "superscript"))
            if actual_runs != expected_runs:
                _invalid("Word rich-text runs or superscript positions differ from the source blocks")

            math_blocks = [block.content for page in document.pages for block in page if block.kind == "math"]
            actual_math = root.xpath(".//m:oMath", namespaces=ns)
            if len(actual_math) != len(math_blocks) or len(math_blocks) != expected_equations:
                _invalid("Word OMML equation count differs from explicit AST equations")
            for expected, actual in zip(math_blocks, actual_math):
                actual_signature = tuple(_xml_signature(child) for child in actual)
                if actual_signature != tuple(_expected_omml(expected)):
                    _invalid("Word OMML structure differs from its math AST")
    except common.WorkflowError:
        raise
    except (OSError, KeyError, zipfile.BadZipFile, etree.XMLSyntaxError, ValueError) as exc:
        raise common.WorkflowError("render_integrity_error", "Word full-text or OMML verification failed") from exc


def _check_fonts(root, recipe):
    font_recipe = recipe["fonts"]
    if type(font_recipe) is not dict or set(font_recipe) != {"face_index", "sources", "licenses"}:
        _invalid("Font recipe is malformed")
    if (type(font_recipe["face_index"]) is not int or font_recipe["face_index"] < 0 or
            type(font_recipe["sources"]) is not dict or set(font_recipe["sources"]) != {"regular", "bold", "math"} or
            type(font_recipe["licenses"]) is not dict or set(font_recipe["licenses"]) != {"cjk", "math"}):
        _invalid("Font recipe source and license records are malformed")
    for records in (font_recipe["sources"], font_recipe["licenses"]):
        for record in records.values():
            if (type(record) is not dict or set(record) != {"sha256", "size"} or
                    type(record["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) or
                    type(record["size"]) is not int or record["size"] < 1):
                _invalid("Font source or license record has an invalid size or hash")
    prepared_path = root / "fonts" / "manifest.json"
    prepared = common.read_json(prepared_path)
    if (type(prepared) is not dict or set(prepared) != {
            "word_family", "cjk_face_index", "characters", "source_hashes", "files", "renamed_family"} or
            prepared["cjk_face_index"] != font_recipe["face_index"] or
            prepared["source_hashes"] != {key: value["sha256"] for key, value in font_recipe["sources"].items()}):
        _invalid("Prepared fonts do not match the recorded font source and face")
    if type(prepared["files"]) is not dict or set(prepared["files"]) != {
            "CJK-Regular.ttf", "CJK-Bold.ttf", "Math.ttf", "cjk-LICENSE.txt", "math-LICENSE.txt"}:
        _invalid("Prepared font file set is invalid")
    for name, expected_sha in prepared["files"].items():
        record = _file_record(root / "fonts" / name)
        if record["sha256"] != expected_sha:
            _invalid("Prepared font or license bytes differ from their manifest")
    for name, path in _LICENSE_FILES.items():
        current = _file_record(path)
        if font_recipe["licenses"].get(name) != current:
            _invalid("Renderer license source changed since this version was built")
    expected_names = set(prepared["files"]) | {"manifest.json"}
    actual_names = {p.name for p in (root / "fonts").iterdir()}
    if actual_names != expected_names:
        _invalid("Prepared font directory has missing or extra members")


def _check_assets(root, content, sources, source_root, recipe):
    declared = {asset["storage_key"]: asset["sha256"] for asset in content["assets"]}
    assets = recipe["assets"]
    if type(assets) is not dict or set(assets) != set(declared):
        _invalid("Recipe asset set differs from content declarations")
    for key, expected_sha in declared.items():
        record = assets[key]
        if (type(record) is not dict or set(record) != {"sha256", "size"} or
                record["sha256"] != expected_sha or type(record["size"]) is not int or record["size"] < 1):
            _invalid("Recipe asset bytes do not match content declarations")
        path = resolve_formula_image({"storage_key": key, "sha256": expected_sha}, root / "assets")
        if _file_record(path) != record:
            _invalid("Packaged resource size or SHA differs from the render recipe")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                if image.mode != "RGB" or image.width * image.height > 4_000_000:
                    _invalid("Resource PNG mode or pixel dimensions are unsupported")
        except common.WorkflowError:
            raise
        except Exception as exc:
            raise common.WorkflowError("invalid_asset", "A packaged resource is not a valid PNG") from exc
    if declared:
        actual = set()
        for current, _, names in os.walk(root / "assets"):
            for name in names:
                actual.add((Path(current) / name).relative_to(root / "assets").as_posix())
        if actual != set(declared):
            _invalid("Packaged resource set differs from content declarations")
    elif (root / "assets").exists():
        _invalid("An undeclared resources directory is not allowed")

    if source_root is not None:
        records = asset_records(content, sources, source_root, root / "assets" if declared else None)
        if records != assets:
            _invalid("Packaged resource bytes or original-pixel provenance do not match")
        return "passed"
    return "not_tested"


def _check_recipe(root, content, sources, manifest):
    recipe = manifest["recipe"]
    fields = {
        "schema_version", "content_sha256", "sources_sha256", "assets", "fonts",
        "code_sha256", "dependencies", "python_version", "backend_version", "renderer_tools",
    }
    if type(recipe) is not dict or set(recipe) != fields or recipe["schema_version"] != "swf.solution-recipe.v1":
        _invalid("Solution recipe has an invalid schema")
    if (recipe["content_sha256"] != content_digest(content) or
            recipe["sources_sha256"] != common.digest(common.canonical(sources)) or
            manifest["content_sha256"] != content_digest(content) or
            manifest["recipe_sha256"] != common.digest(common.canonical(recipe))):
        _invalid("Content, sources or recipe digest differs from the solution manifest")
    if recipe["backend_version"] != GENERATOR_VERSION or recipe["python_version"] != platform.python_version():
        _invalid("Renderer or Python version differs from the recorded recipe")
    if recipe["code_sha256"] != code_records():
        _invalid("Renderer or helper source changed since this version was rendered")
    if recipe["dependencies"] != _dependency_versions():
        _invalid("Renderer dependency versions differ from the recorded recipe")
    if recipe["renderer_tools"] != {"pdftoppm": _pdftoppm_version()}:
        _invalid("Renderer tool versions differ from the recorded recipe")
    _check_fonts(root, recipe)


def _verify_companion(version_dir, expected_directory_name=None, source_root=None):
    root = Path(os.path.abspath(version_dir))
    common.assert_no_symlinks(root)
    if root.is_symlink() or not root.is_dir():
        _invalid("Version path must be a real directory")
    manifest_path = root / "solution-manifest.json"
    manifest = common.read_json(manifest_path)
    if (type(manifest) is not dict or set(manifest) != {
            "schema_version", "recipe", "content_sha256", "recipe_sha256", "documents", "files"} or
            manifest["schema_version"] != "swf.solution-render.v1"):
        _invalid("Solution manifest has an invalid schema")
    if manifest_path.read_bytes() != common.canonical(manifest) + b"\n":
        _invalid("Solution manifest is not in canonical form")
    content = common.read_json(root / "content.json")
    sources = common.read_json(root / "sources.json")
    for filename, value in (("content.json", content), ("sources.json", sources)):
        if (root / filename).read_bytes() != common.canonical(value) + b"\n":
            _invalid("Stored input snapshot is not in canonical form")
    validate_content(content, sources)
    plans = compile_documents(content)
    expected_files = {
        "content.json", "sources.json", "documents-content.json", "fonts/manifest.json",
        "fonts/CJK-Regular.ttf", "fonts/CJK-Bold.ttf", "fonts/Math.ttf",
        "fonts/cjk-LICENSE.txt", "fonts/math-LICENSE.txt",
    }
    for asset in content["assets"]:
        expected_files.add("assets/" + asset["storage_key"])
    for plan in plans:
        document_id = plan["document"].document_id
        expected_files.update({
            f"documents/{document_id}/document.pdf",
            f"documents/{document_id}/document.docx",
        })
        expected_files.update(
            f"previews/{document_id}-{index:03d}.png"
            for index in range(1, len(plan["document"].pages) + 1)
        )
        expected_files.update(
            "delivery/" + plan["delivery_stem"] + "." + format_name
            for format_name in plan["formats"]
        )
    if set(manifest["files"]) != expected_files:
        _invalid("Package file set differs from the complete compiler-derived member set")
    _check_files(root, manifest)
    recipe_name = manifest["recipe_sha256"][:24] if type(manifest["recipe_sha256"]) is str else ""
    expected_name = expected_directory_name or root.name
    if recipe_name != expected_name:
        _invalid("Version directory name does not match the recipe digest")
    _check_recipe(root, content, sources, manifest)

    stored_docs = common.read_json(root / "documents-content.json")
    expected_docs = {
        "schema_version": "swf.solution-documents.v1",
        "documents": [
            {"document_id": plan["document"].document_id,
             "document": document_dict(plan["document"])}
            for plan in plans
        ],
    }
    if stored_docs != expected_docs or (root / "documents-content.json").read_bytes() != common.canonical(expected_docs) + b"\n":
        _invalid("Stored compiled documents do not match current content and compiler output")
    descriptors = manifest["documents"]
    if type(descriptors) is not list or len(descriptors) != len(plans):
        _invalid("Manifest document list differs from the compiler plan")

    all_page_count = 0
    expected_delivery = set()
    body_page_groups = {}
    for plan, descriptor in zip(plans, descriptors):
        if type(descriptor) is not dict or set(descriptor) != _DOCUMENT_FIELDS:
            _invalid("Document manifest entry has an invalid field set")
        document = plan["document"]
        page_count = len(document.pages)
        previews = [f"previews/{document.document_id}-{index:03d}.png" for index in range(1, page_count + 1)]
        expected = {
            "document_id": document.document_id,
            "title": document.title,
            "purpose": document.purpose,
            "page_count": page_count,
            "word_equations": sum(block.kind == "math" for page in document.pages for block in page),
            "delivery_stem": plan["delivery_stem"],
            "formats": list(plan["formats"]),
            "question_ids": list(plan["question_ids"]),
            "page_questions": list(plan["page_questions"]),
            "previews": previews,
        }
        if descriptor != expected:
            _invalid("Document descriptor differs from the explicit compiler plan")
        pdf_relative = f"documents/{document.document_id}/document.pdf"
        docx_relative = f"documents/{document.document_id}/document.docx"
        preview_paths = [root / item for item in previews]
        packet_verify._pdf_report(
            root / pdf_relative, document, {"pages": page_count}, preview_paths,
        )
        _check_pdf_text(root / pdf_relative, document)
        _check_word(root / docx_relative, document, descriptor["word_equations"])
        try:
            with fitz.open(root / pdf_relative) as pdf:
                question_page_indices = {}
                for index, question_id in enumerate(plan["page_questions"]):
                    if question_id is None:
                        continue
                    local_index = question_page_indices.get(question_id, 0) + 1
                    question_page_indices[question_id] = local_index
                    page = pdf[index]
                    body = page.get_pixmap(
                        matrix=fitz.Matrix(1.5, 1.5),
                        clip=fitz.Rect(0, 0, page.rect.width, 799),
                        alpha=False,
                    ).tobytes("png")
                    body_page_groups.setdefault((question_id, local_index), []).append(body)
        except common.WorkflowError:
            raise
        except Exception as exc:
            raise common.WorkflowError("render_integrity_error", "Could not compare repeated question-page bodies") from exc
        for format_name in plan["formats"]:
            relative = "delivery/" + plan["delivery_stem"] + "." + format_name
            expected_delivery.add(relative)
            if _file_record(root / relative) != _file_record(root / (pdf_relative if format_name == "pdf" else docx_relative)):
                _invalid("Selected delivery file differs from its verified internal render")
        all_page_count += page_count

    for page_instances in body_page_groups.values():
        if any(image != page_instances[0] for image in page_instances[1:]):
            _invalid("Repeated question-page bodies differ across organization documents")
    unique_body_pages = len(body_page_groups)
    replica_pages = sum(max(0, len(instances) - 1) for instances in body_page_groups.values())

    files = set(manifest["files"])
    actual_delivery = {name for name in files if name.startswith("delivery/")}
    if actual_delivery != expected_delivery:
        _invalid("Delivery directory contains missing, unselected or extra formats")
    source_status = _check_assets(root, content, sources, source_root, manifest["recipe"])
    if source_root is not None:
        verify_sources(sources, source_root)
    report = {
        "status": "passed",
        "content_sha256": manifest["content_sha256"],
        "recipe_sha256": manifest["recipe_sha256"],
        "documents": len(plans),
        "pdf_pages": all_page_count,
        "unique_body_pages": unique_body_pages,
        "replica_pages": replica_pages,
        "source_originals": source_status,
        "human_review": "not_tested",
        "word_client": "not_tested",
    }
    return report, manifest


def verify_companion(version_dir, source_root=None) -> dict:
    """Verify immutable package bytes and machine-render structure only."""
    try:
        return _verify_companion(version_dir, source_root=source_root)[0]
    except common.WorkflowError:
        raise
    except ExportError as exc:
        raise common.WorkflowError(exc.code, str(exc)) from exc
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError,
            zipfile.BadZipFile) as exc:
        raise common.WorkflowError("render_integrity_error", "Companion package could not be verified") from exc
