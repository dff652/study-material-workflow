"""Render solution-companion documents into immutable private versions."""
from __future__ import annotations

import copy
import fcntl
import os
from pathlib import Path
import platform
import shutil
import tempfile

import workflow_common as common
from collect_sources import verify_sources
from print_backend.contracts import ExportError, GENERATOR_VERSION, document_dict
from print_backend.fonts import prepare_fonts
from print_backend.renderer import render_document
from render_packet import (
    _LICENSE_FILES,
    _acquire_lock,
    _create_previews,
    _dependency_versions,
    _file_record,
    _font_inputs,
    _pdftoppm_version,
    _rename_noreplace,
    _set_private_modes,
)

from .model import asset_records, code_records, compile_documents, content_digest, validate_content


_SCRIPT_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE_LIMIT = 512 * 1024 * 1024


def _overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _check_output_roots(output, source_root, asset_root):
    output = Path(os.path.abspath(output))
    common.assert_no_symlinks(output)
    output_resolved = output.resolve()
    for value, label in ((source_root, "source"), (asset_root, "asset")):
        if value is None:
            continue
        root = common.root_path(value)
        if _overlap(output_resolved, root):
            common.fail("source_output_overlap", f"Output root overlaps the configured {label} root")
    return output


def _file_records(root):
    result = {}
    total = 0
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        for name in dirs:
            child = here / name
            if child.is_symlink() or not child.is_dir():
                common.fail("invalid_output_file", "Version contains a symlink or invalid directory")
        for name in names:
            child = here / name
            if child.is_symlink() or not child.is_file():
                common.fail("invalid_output_file", "Version contains a symlink or non-file entry")
            relative = child.relative_to(root).as_posix()
            if relative == "solution-manifest.json":
                continue
            total += child.stat().st_size
            if total > _PACKAGE_LIMIT:
                common.fail("package_too_large", "Rendered version exceeds the verification size limit")
            result[relative] = _file_record(child)
    return dict(sorted(result.items()))


def _source_snapshot(sources):
    return common.digest(common.canonical(sources))


def _recipe(content, sources, assets, font_sources, face_index, license_sources):
    return {
        "schema_version": "swf.solution-recipe.v1",
        "content_sha256": content_digest(content),
        "sources_sha256": _source_snapshot(sources),
        "assets": assets,
        "fonts": {
            "face_index": face_index,
            "sources": font_sources,
            "licenses": license_sources,
        },
        "code_sha256": code_records(),
        "dependencies": _dependency_versions(),
        "python_version": platform.python_version(),
        "backend_version": GENERATOR_VERSION,
        "renderer_tools": {"pdftoppm": _pdftoppm_version()},
    }


def _copy_assets(stage, assets, asset_root):
    if not assets:
        return None
    asset_dir = stage / "assets"
    asset_dir.mkdir(mode=0o700)
    for key, expected in assets.items():
        source = common.resolve_under(asset_root, key)
        if _file_record(source) != expected:
            common.fail("asset_hash_mismatch", "A resource changed while the version was being prepared")
        target = asset_dir / key
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source, target)
        target.chmod(0o600)
        if _file_record(target) != expected:
            common.fail("asset_hash_mismatch", "A copied resource differs from its source bytes")
    return asset_dir


def _copy_delivery_file(source, stage, relative):
    target = stage / "delivery" / relative
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, target)
    target.chmod(0o600)


def _render_stage(stage, content, sources, source_root, asset_root, font_paths,
                  font_sources, face_index, assets, recipe, recipe_sha256):
    common.write_json(stage / "content.json", content)
    common.write_json(stage / "sources.json", sources)
    plans = compile_documents(content)
    common.write_json(stage / "documents-content.json", {
        "schema_version": "swf.solution-documents.v1",
        "documents": [
            {"document_id": plan["document"].document_id,
             "document": document_dict(plan["document"])}
            for plan in plans
        ],
    })

    asset_package_root = _copy_assets(stage, assets, asset_root)
    font_dir = stage / "fonts"
    documents = [plan["document"] for plan in plans]
    fonts, prepared = prepare_fonts(
        documents, font_dir,
        regular_source=font_paths["regular"],
        bold_source=font_paths["bold"],
        math_source=font_paths["math"],
        cjk_notice=_LICENSE_FILES["cjk"],
        math_notice=_LICENSE_FILES["math"],
        face_index=face_index,
    )
    if prepared["source_hashes"] != {role: record["sha256"] for role, record in font_sources.items()}:
        common.fail("font_changed", "A font source changed while the companion was being prepared")
    common.write_json(font_dir / "manifest.json", prepared)

    manifest_documents = []
    for plan in plans:
        document = plan["document"]
        relative_dir = Path("documents") / document.document_id
        rendered = render_document(
            document, stage / relative_dir, fonts, asset_root=asset_package_root,
        )
        previews = _create_previews(rendered["pdf"], stage, document.document_id)
        for format_name in plan["formats"]:
            source = rendered["pdf"] if format_name == "pdf" else rendered["docx"]
            _copy_delivery_file(source, stage, plan["delivery_stem"] + "." + format_name)
        manifest_documents.append({
            "document_id": document.document_id,
            "title": document.title,
            "purpose": document.purpose,
            "page_count": rendered["page_count"],
            "word_equations": rendered["word_equations"],
            "delivery_stem": plan["delivery_stem"],
            "formats": list(plan["formats"]),
            "question_ids": list(plan["question_ids"]),
            "page_questions": list(plan["page_questions"]),
            "previews": previews,
        })

    if code_records() != recipe["code_sha256"] or _dependency_versions() != recipe["dependencies"]:
        common.fail("renderer_changed", "Renderer code or dependencies changed during package creation")
    if _source_snapshot(sources) != recipe["sources_sha256"]:
        common.fail("source_changed", "Source manifest changed while the companion was being prepared")
    if source_root is not None:
        verify_sources(sources, source_root)

    manifest = {
        "schema_version": "swf.solution-render.v1",
        "recipe": recipe,
        "content_sha256": content_digest(content),
        "recipe_sha256": recipe_sha256,
        "documents": manifest_documents,
        "files": _file_records(stage),
    }
    common.write_json(stage / "solution-manifest.json", manifest)
    _set_private_modes(stage)
    return manifest


def _reuse_existing(directory, recipe, recipe_sha256, source_root=None):
    if not directory.exists() and not directory.is_symlink():
        return None
    if directory.is_symlink() or not directory.is_dir():
        common.fail("output_conflict", "The immutable version path exists and is not a real directory")
    from .verify import _verify_companion
    report, manifest = _verify_companion(
        directory, expected_directory_name=directory.name, source_root=source_root,
    )
    if manifest["recipe_sha256"] != recipe_sha256 or manifest["recipe"] != recipe:
        common.fail("version_collision", "An existing recipe key has different immutable content")
    return report


def render_companion(content, sources, source_root, font_config, output_root,
                     asset_root=None) -> dict:
    """Render both internal formats, publish requested delivery formats atomically."""
    try:
        content_snapshot = copy.deepcopy(content)
        sources_snapshot = copy.deepcopy(sources)
        validate_content(content_snapshot, sources_snapshot)
        verify_sources(sources_snapshot, source_root)
        if content_snapshot["assets"] and asset_root is None:
            common.fail("missing_asset_root", "Assets require an explicit private asset root")
        output = _check_output_roots(output_root, source_root, asset_root)
        output.mkdir(parents=True, exist_ok=True, mode=0o700)
        output.chmod(0o700)
        assets = asset_records(content_snapshot, sources_snapshot, source_root, asset_root) if content_snapshot["assets"] else {}
        compile_documents(content_snapshot)
        font_paths, face_index, font_sources, license_sources = _font_inputs(font_config)
        recipe = _recipe(content_snapshot, sources_snapshot, assets, font_sources, face_index, license_sources)
        recipe_sha256 = common.digest(common.canonical(recipe))
        version_name = recipe_sha256[:24]
        final = output / version_name

        reused_report = _reuse_existing(final, recipe, recipe_sha256, source_root)
        if reused_report is not None:
            manifest = common.read_json(final / "solution-manifest.json")
            return {
                "directory": str(final), "content_sha256": manifest["content_sha256"],
                "recipe_sha256": recipe_sha256, "documents": manifest["documents"],
                "delivery_files": sorted(
                    "delivery/" + doc["delivery_stem"] + "." + fmt
                    for doc in manifest["documents"] for fmt in doc["formats"]
                ),
                "reused": True,
            }

        lock_fd = _acquire_lock(output / f".{version_name}.lock")
        try:
            reused_report = _reuse_existing(final, recipe, recipe_sha256, source_root)
            if reused_report is not None:
                manifest = common.read_json(final / "solution-manifest.json")
                return {
                    "directory": str(final), "content_sha256": manifest["content_sha256"],
                    "recipe_sha256": recipe_sha256, "documents": manifest["documents"],
                    "delivery_files": sorted(
                        "delivery/" + doc["delivery_stem"] + "." + fmt
                        for doc in manifest["documents"] for fmt in doc["formats"]
                    ),
                    "reused": True,
                }

            stage = Path(tempfile.mkdtemp(prefix=f".{version_name}.stage-", dir=output))
            try:
                _render_stage(
                    stage, content_snapshot, sources_snapshot, source_root, asset_root,
                    font_paths, font_sources, face_index, assets,
                    recipe, recipe_sha256,
                )
                from .verify import _verify_companion
                report, manifest = _verify_companion(
                    stage, expected_directory_name=version_name, source_root=source_root,
                )
                if manifest["recipe"] != recipe or manifest["recipe_sha256"] != recipe_sha256:
                    common.fail("manifest_changed", "Solution manifest changed before publication")
                _rename_noreplace(stage, final)
                stage = None
                return {
                    "directory": str(final), "content_sha256": manifest["content_sha256"],
                    "recipe_sha256": recipe_sha256, "documents": manifest["documents"],
                    "delivery_files": sorted(
                        "delivery/" + doc["delivery_stem"] + "." + fmt
                        for doc in manifest["documents"] for fmt in doc["formats"]
                    ),
                    "reused": False,
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
        raise common.WorkflowError("render_failed", "Companion could not be rendered into an immutable version") from exc
