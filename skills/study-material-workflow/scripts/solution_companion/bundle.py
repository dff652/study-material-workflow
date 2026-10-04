"""Create a checked ZIP containing only selected companion delivery files."""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile
import zipfile

import workflow_common as common

from .model import validate_review
from .verify import verify_companion


_BUNDLE_LIMIT = 128 * 1024 * 1024


def _review_statuses(review):
    values = [review[key]["status"] for key in ("content", "math", "pdf_visual", "word_client")]
    values.extend(platform["status"] for platform in review["word_client"]["platforms"].values())
    values.extend(item["status"] for item in review["independent_reviews"])
    return values


def _write_new_file(path, raw):
    path = Path(path)
    common.assert_no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".bundle-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if not path.is_file() or path.read_bytes() != raw:
                common.fail("output_conflict", "Existing bundle differs; choose a new output path")
    finally:
        Path(temporary).unlink(missing_ok=True)


def bundle_companion(version_dir, output, review=None) -> dict:
    """Bundle the selected formats; review failures are diagnostic and block delivery."""
    root = Path(os.path.abspath(version_dir))
    common.assert_no_symlinks(root)
    root = root.resolve(strict=True)
    report = verify_companion(root)
    manifest = common.read_json(root / "solution-manifest.json")
    content = common.read_json(root / "content.json")
    if review is not None:
        validate_review(review, content, manifest["recipe_sha256"], manifest["documents"])
        if "fail" in _review_statuses(review):
            common.fail("review_failed", "A failed review blocks bundling; preserve the version for diagnosis")

    members = {}
    for document in manifest["documents"]:
        for format_name in document["formats"]:
            relative = "delivery/" + document["delivery_stem"] + "." + format_name
            members[relative] = (root / relative).read_bytes()
    members["solution-manifest.json"] = (root / "solution-manifest.json").read_bytes()
    members["verify-summary.json"] = common.canonical(report) + b"\n"
    for name in ("cjk-LICENSE.txt", "math-LICENSE.txt"):
        members["licenses/" + name] = (root / "fonts" / name).read_bytes()
    if review is None:
        review_summary = "External review: not_tested (no review record supplied)."
    else:
        review_summary = "External review statuses: " + ", ".join(
            key + "=" + review[key]["status"] for key in ("content", "math", "pdf_visual", "word_client")
        ) + "."
    members["README.txt"] = (
        "Study-material solution companion\n"
        "Package state: draft; machine_verified does not mean human-approved or released.\n"
        + review_summary + "\n"
        + "PDF visual review and Word client acceptance are separate human checks. "
          "This archive does not claim either check unless the attached review says so.\n"
        + "Per-question, per-lecture and combined files reuse the same question-page bodies; organization outputs repeat those pages.\n"
        + "Word files reference but do not embed the selected fonts. PC/macOS Word font-substitution and pagination experiments remain separate acceptance checks.\n"
        + "Source originals were not rechecked during bundle creation; see verify-summary.json.\n"
        + "Selected output formats only; source photographs and unrequested formats are excluded.\n"
    ).encode("utf-8")
    if review is not None:
        members["review.json"] = common.canonical(review) + b"\n"

    records = {
        name: {"sha256": common.digest(raw), "size": len(raw)}
        for name, raw in sorted(members.items())
    }
    if sum(record["size"] for record in records.values()) > _BUNDLE_LIMIT:
        common.fail("bundle_too_large", "Selected delivery files exceed the bounded ZIP size")
    members["bundle-files.json"] = common.canonical({
        "schema_version": "swf.solution-bundle-files.v1", "files": records,
    }) + b"\n"
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(members.items()):
            if not name or "\\" in name or name.startswith("/") or ".." in Path(name).parts:
                common.fail("invalid_bundle_path", "Bundle member path is not canonical")
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, raw)
    zip_bytes = stream.getvalue()
    if len(zip_bytes) > _BUNDLE_LIMIT:
        common.fail("bundle_too_large", "Compressed ZIP exceeds the bounded output size")

    try:
        with zipfile.ZipFile(BytesIO(zip_bytes), "r") as archive:
            names = archive.namelist()
            if (archive.testzip() is not None or len(names) != len(set(names)) or
                    set(names) != set(members)):
                common.fail("bundle_invalid", "ZIP CRC or member set verification failed")
            for name, expected in members.items():
                if archive.read(name) != expected:
                    common.fail("bundle_invalid", "ZIP readback differs from selected package bytes")
    except zipfile.BadZipFile as exc:
        raise common.WorkflowError("bundle_invalid", "Generated ZIP could not be reopened") from exc

    output = Path(os.path.abspath(output))
    common.assert_no_symlinks(output)
    if output == root or output.is_dir():
        common.fail("invalid_output", "Bundle output must be a file outside the immutable version")
    if output.resolve().is_relative_to(root):
        common.fail("source_output_overlap", "Bundle output may not be placed inside its immutable version")
    checksum_path = Path(str(output) + ".checksum.json")
    common.assert_no_symlinks(checksum_path)
    reused = output.exists()
    if reused:
        if not output.is_file() or output.read_bytes() != zip_bytes:
            common.fail("output_conflict", "Existing ZIP differs; use a new output version")
    else:
        _write_new_file(output, zip_bytes)

    checksum = {
        "schema_version": "swf.solution-bundle.v1",
        "zip_sha256": common.digest(zip_bytes),
        "zip_size": len(zip_bytes),
        "files": len(members),
        "recipe_sha256": manifest["recipe_sha256"],
        "review_status": "not_tested" if review is None else "attached",
        "unique_body_pages": report["unique_body_pages"],
        "replica_pages": report["replica_pages"],
    }
    common.write_json(checksum_path, checksum)
    return {"output": str(output), "reused": reused, **checksum}
