"""Render a packet into an immutable, content-addressed PDF and Word package."""
from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import tempfile
import copy

import pymupdf as fitz
from PIL import Image

import workflow_common as common
from packet import asset_records, packet_digest, validate_packet
from print_backend.contracts import ExportError, GENERATOR_VERSION, FontSet, document_from_dict
from print_backend.fonts import prepare_fonts
from print_backend.renderer import render_document


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
_SCRIPT_DIR = Path(__file__).resolve().parent
_ASSET_DIR = _SCRIPT_DIR.parent / "assets"
_LICENSE_FILES = {"cjk": _ASSET_DIR / "Noto-OFL.txt", "math": _ASSET_DIR / "DejaVu-fonts.txt"}
_FONT_KEYS = {"regular": "regular_source", "bold": "bold_source", "math": "math_source"}


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        common.fail("invalid_arguments", "Command-line arguments do not match the tool contract")


def _regular_file(path, code):
    path = Path(path)
    common.assert_no_symlinks(path)
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise OSError("not a regular file")
        return resolved
    except OSError as exc:
        raise common.WorkflowError(code, "A required local file is missing or unreadable") from exc


def _file_record(path):
    path = _regular_file(path, "missing_input_file")
    raw = path.read_bytes()
    return {"sha256": common.digest(raw), "size": len(raw)}


def _font_inputs(font_config):
    if (not isinstance(font_config, dict) or
            set(font_config) != {"regular_source", "bold_source", "math_source", "face_index"}):
        common.fail("invalid_font_config", "Font config must name regular, bold and math sources plus face_index")
    face_index = font_config["face_index"]
    if type(face_index) is not int or face_index < 0:
        common.fail("invalid_font_config", "face_index must be a non-negative integer")
    paths = {}
    records = {}
    for role, key in _FONT_KEYS.items():
        value = font_config[key]
        if not isinstance(value, str) or not value.strip():
            common.fail("invalid_font_config", f"{key} must be a local file path")
        paths[role] = _regular_file(value, "missing_font")
        records[role] = _file_record(paths[role])
    license_records = {name: _file_record(path) for name, path in _LICENSE_FILES.items()}
    return paths, face_index, records, license_records


def _code_records():
    records = {}
    for relative in _CODE_FILES:
        path = _SCRIPT_DIR / relative
        records[relative] = _file_record(path)["sha256"]
    return records


def _dependency_versions():
    versions = {}
    for name in _DEPENDENCIES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise common.WorkflowError("missing_dependency", f"Required renderer dependency is missing: {name}") from exc
    return versions


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


def _recipe(packet_sha256, packet_record_sha256, assets, font_sources, face_index, license_sources):
    return {
        "schema_version": "swf.render-recipe.v1",
        "packet_sha256": packet_sha256,
        "packet_record_sha256": packet_record_sha256,
        "assets": assets,
        "fonts": {
            "face_index": face_index,
            "sources": font_sources,
            "licenses": license_sources,
        },
        "code_sha256": _code_records(),
        "dependencies": _dependency_versions(),
        "python_version": platform.python_version(),
        "backend_version": GENERATOR_VERSION,
        "renderer_tools": {"pdftoppm": _pdftoppm_version()},
    }


def _set_private_modes(root):
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in dirs:
            child = current_path / name
            if child.is_symlink():
                common.fail("symlink_path", "Package output may not contain symlinks")
            child.chmod(0o700)
        for name in files:
            child = current_path / name
            if child.is_symlink() or not child.is_file():
                common.fail("invalid_output_file", "Package output must contain regular files only")
            child.chmod(0o600)
    Path(root).chmod(0o700)


def _package_files(root):
    result = {}
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        if any((current_path / name).is_symlink() for name in dirs):
            common.fail("symlink_path", "Package output may not contain symlink directories")
        for name in files:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                common.fail("invalid_output_file", "Package output must contain regular files only")
            relative = path.relative_to(root).as_posix()
            if relative == "render-manifest.json":
                continue
            result[relative] = _file_record(path)
    return dict(sorted(result.items()))


def _asset_paths(packet, asset_root):
    records = asset_records(packet, asset_root)
    paths = {}
    for key, record in records.items():
        if Path(key).as_posix() != key or "\\" in key:
            common.fail("invalid_asset_key", "Asset storage keys must use normalized relative paths")
        paths[key] = common.resolve_under(asset_root, key)
        if _file_record(paths[key]) != record:
            common.fail("asset_hash_mismatch", "An asset changed while the packet was being prepared")
    return records, paths


def _copy_assets(root, assets, asset_paths):
    for key, source in asset_paths.items():
        destination = root / "assets" / key
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        raw = source.read_bytes()
        if common.digest(raw) != assets[key]["sha256"] or len(raw) != assets[key]["size"]:
            common.fail("asset_hash_mismatch", "An asset changed while it was being copied")
        destination.write_bytes(raw)
        destination.chmod(0o600)


def _create_previews(pdf_path, root, document_id):
    previews = []
    try:
        with fitz.open(pdf_path) as pdf:
            for index, page in enumerate(pdf, 1):
                relative = f"previews/{document_id}-{index:03d}.png"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(target)
                target.chmod(0o600)
                with Image.open(target) as image:
                    image.verify()
                previews.append(relative)
    except Exception as exc:
        raise common.WorkflowError("preview_generation_failed", "Could not create every PDF page preview") from exc
    return previews


def _rename_noreplace(source, destination):
    """Publish a complete directory atomically without replacing any existing key."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        common.fail("atomic_publish_unavailable", "This platform lacks atomic no-replace directory publication")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    result = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        common.fail("output_conflict", "The immutable version directory already exists")
    raise OSError(error, os.strerror(error), str(destination))


def _acquire_lock(path):
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise common.WorkflowError("render_lock_error", "Could not safely open the renderer lock") from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            common.fail("render_lock_error", "Renderer lock must be a regular file")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise common.WorkflowError("render_in_progress", "Another process is preparing this immutable version") from exc
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _reuse_existing(directory, recipe, recipe_sha256):
    if not directory.exists() and not directory.is_symlink():
        return None
    if directory.is_symlink() or not directory.is_dir():
        common.fail("output_conflict", "The immutable version path exists and is not a real directory")
    from verify_packet import _verify_package
    report, manifest = _verify_package(directory, expected_directory_name=directory.name)
    if manifest["recipe_sha256"] != recipe_sha256 or manifest["recipe"] != recipe:
        common.fail("version_collision", "An existing recipe key has different immutable content")
    return report


def render_packet(packet, font_config, output_root, asset_root=None) -> dict:
    """Render, machine-verify and atomically publish an immutable packet version."""
    try:
        packet_snapshot = copy.deepcopy(packet)
        validate_packet(packet_snapshot)
        documents = [document_from_dict(value) for value in packet_snapshot["documents"]]
        packet_sha256 = packet_digest(packet_snapshot)
        packet_record_sha256 = common.digest(common.canonical(packet_snapshot))
        assets, asset_paths = _asset_paths(packet_snapshot, asset_root)
        font_paths, face_index, font_sources, license_sources = _font_inputs(font_config)
        recipe = _recipe(packet_sha256, packet_record_sha256, assets, font_sources, face_index, license_sources)
        recipe_sha256 = common.digest(common.canonical(recipe))
        version_name = recipe_sha256[:24]

        output = Path(os.path.abspath(output_root))
        common.assert_no_symlinks(output)
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not output.is_dir():
            common.fail("invalid_output_root", "Output root must be a directory")
        output.chmod(0o700)
        final = output / version_name
        existing_report = _reuse_existing(final, recipe, recipe_sha256)
        if existing_report is not None:
            return {
                "directory": str(final), "recipe_sha256": recipe_sha256,
                "packet_sha256": packet_sha256, "documents": existing_report["documents"],
                "pdf_pages": existing_report["pdf_pages"], "reused": True,
            }

        lock = output / f".{version_name}.lock"
        lock_fd = _acquire_lock(lock)
        try:
            existing_report = _reuse_existing(final, recipe, recipe_sha256)
            if existing_report is not None:
                return {
                    "directory": str(final), "recipe_sha256": recipe_sha256,
                    "packet_sha256": packet_sha256, "documents": existing_report["documents"],
                    "pdf_pages": existing_report["pdf_pages"], "reused": True,
                }

            stage = Path(tempfile.mkdtemp(prefix=f".{version_name}.stage-", dir=output))
            try:
                common.write_json(stage / "packet.json", packet_snapshot)
                asset_dir = stage / "assets"
                if asset_paths:
                    asset_dir.mkdir(mode=0o700)
                    _copy_assets(stage, assets, asset_paths)
                font_output = stage / "fonts"
                fonts, prepared = prepare_fonts(
                    documents, font_output,
                    regular_source=font_paths["regular"],
                    bold_source=font_paths["bold"],
                    math_source=font_paths["math"],
                    cjk_notice=_LICENSE_FILES["cjk"],
                    math_notice=_LICENSE_FILES["math"],
                    face_index=face_index,
                )
                if prepared["source_hashes"] != {role: record["sha256"] for role, record in font_sources.items()}:
                    common.fail("font_changed", "A font source changed while the packet was being prepared")
                common.write_json(font_output / "manifest.json", prepared)

                manifest_documents = []
                total_pages = 0
                documents_root = stage / "documents"
                documents_root.mkdir(mode=0o700)
                asset_package_root = stage / "assets" if asset_paths else None
                for document in documents:
                    relative_dir = Path("documents") / document.document_id
                    rendered = render_document(
                        document, stage / relative_dir, fonts, asset_root=asset_package_root,
                    )
                    pdf_relative = (relative_dir / "document.pdf").as_posix()
                    docx_relative = (relative_dir / "document.docx").as_posix()
                    previews = _create_previews(rendered["pdf"], stage, document.document_id)
                    manifest_documents.append({
                        "document_id": document.document_id,
                        "purpose": document.purpose,
                        "pdf": pdf_relative,
                        "docx": docx_relative,
                        "pages": rendered["page_count"],
                        "previews": previews,
                    })
                    total_pages += rendered["page_count"]

                if _code_records() != recipe["code_sha256"] or _dependency_versions() != recipe["dependencies"]:
                    common.fail("renderer_changed", "Renderer code or dependencies changed during package creation")
                manifest = {
                    "schema_version": "swf.render.v1",
                    "packet_sha256": packet_sha256,
                    "recipe_sha256": recipe_sha256,
                    "recipe": recipe,
                    "documents": manifest_documents,
                    "files": _package_files(stage),
                }
                common.write_json(stage / "render-manifest.json", manifest)
                _set_private_modes(stage)

                from verify_packet import _verify_package
                report, checked_manifest = _verify_package(stage, expected_directory_name=version_name)
                if checked_manifest != manifest:
                    common.fail("manifest_changed", "Render manifest changed before publication")
                _rename_noreplace(stage, final)
                stage = None
                return {
                    "directory": str(final), "recipe_sha256": recipe_sha256,
                    "packet_sha256": packet_sha256, "documents": report["documents"],
                    "pdf_pages": report["pdf_pages"], "reused": False,
                }
            finally:
                if stage is not None and stage.exists():
                    shutil.rmtree(stage)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
    except common.WorkflowError:
        raise
    except ExportError as exc:
        raise common.WorkflowError(exc.code, str(exc)) from exc
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise common.WorkflowError("render_failed", "Packet could not be rendered into a verified package") from exc


def _main(argv=None):
    def run():
        parser = _JsonArgumentParser(description=__doc__)
        parser.add_argument("--packet", required=True)
        parser.add_argument("--font-config", required=True)
        parser.add_argument("--output-root", required=True)
        parser.add_argument("--asset-root")
        args = parser.parse_args(argv)
        return render_packet(
            common.read_json(args.packet), common.read_json(args.font_config),
            args.output_root, asset_root=args.asset_root,
        )
    return common.cli_result(run)


if __name__ == "__main__":
    raise SystemExit(_main())
