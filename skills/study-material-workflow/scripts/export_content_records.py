#!/usr/bin/env python3
"""Build a bounded Workbench companion package from explicit typed content."""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import warnings
import xml.etree.ElementTree as ET

from PIL import Image, UnidentifiedImageError

from print_backend.contracts import ExportError, validate_math
from workflow_common import (WorkflowArgumentParser, WorkflowError, canonical, cli_result, digest,
                             fail, read_json, resolve_under, root_path, assert_no_symlinks)


CONTENT_SCHEMA = "swf.workbench-content.v1"
OUTPUT_SCHEMA = "swb.skill-records.v2"
MAX_ASSET_BYTES = 512 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_RECORDS = 300
MAX_INPUT_BYTES = 1024 * 1024
ASSET_MEDIA = {".png": "image/png", ".svg": "image/svg+xml", ".pdf": "application/pdf"}
NODE_FIELDS = {
    "knowledge": {"definition", "conditions", "common_errors"},
    "method": {"name", "conditions", "steps", "notes"},
    "question_type": {"name", "conditions", "structural_features"},
}
_ID_RE = re.compile(r"[\w.-]{1,100}\Z")
_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SVG_FORBIDDEN = {"script", "foreignObject", "image", "use", "a", "animate", "animateMotion",
                  "animateTransform", "set", "audio", "video", "iframe", "object", "embed", "feImage"}


def _invalid(code: str, message: str) -> None:
    fail(code, message)


def _bounded_json(value, max_depth: int = 100) -> None:
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > max_depth:
            _invalid("invalid_content", "JSON nesting exceeds the supported depth")
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)


def _local_id(value, label: str) -> str:
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        _invalid("invalid_identity", f"{label} must be a bounded local ID")
    return value


def _text(value, limit: int, label: str, *, allow_empty: bool = False) -> None:
    if (type(value) is not str or len(value) > limit or "\x00" in value or
            (not allow_empty and not value.strip())):
        _invalid("invalid_content", f"{label} must be bounded explicit text")


def _validate_sources(sources) -> dict:
    """Validate the source identity data needed for exact region checks.

    Existing source manifests may carry collection-specific metadata. The
    exporter consumes only source_id, sha256, width and height and never copies
    or derives those facts from an image or diagram asset.
    """
    required = {"schema_version", "batch_id", "sources"}
    if (type(sources) is not dict or not required <= set(sources) or
            set(sources) - required - {"expected_counts"} or sources["schema_version"] != "swf.sources.v1"):
        _invalid("invalid_sources", "Expected a bounded swf.sources.v1 manifest")
    if type(sources["batch_id"]) is not str or not sources["batch_id"].strip():
        _invalid("invalid_sources", "Source manifest batch_id must be explicit")
    rows = sources["sources"]
    if type(rows) is not list or not 1 <= len(rows) <= 100:
        _invalid("invalid_sources", "Source manifest must contain 1 to 100 images")
    expected = sources.get("expected_counts")
    if (expected is not None and
            (type(expected) is not dict or any(type(value) is not int or value < 0 for value in expected.values()))):
        _invalid("invalid_sources", "Source expected counts must be non-negative integers")
    source_map = {}
    for row in rows:
        if type(row) is not dict or not {"source_id", "sha256", "width", "height"} <= set(row):
            _invalid("invalid_sources", "Each source needs ID, SHA-256 and known dimensions")
        source_id = row["source_id"]
        if (type(source_id) is not str or _ID_RE.fullmatch(source_id) is None or source_id in source_map or
                type(row["sha256"]) is not str or _SHA_RE.fullmatch(row["sha256"]) is None or
                type(row["width"]) is not int or row["width"] < 1 or
                type(row["height"]) is not int or row["height"] < 1):
            _invalid("invalid_sources", "Source identity, SHA-256 or dimensions are invalid")
        source_map[source_id] = row
    if expected is not None and "sources" in expected and expected["sources"] != len(rows):
        _invalid("invalid_sources", "Source count does not match expected_counts")
    return source_map


def _source_refs(refs, source_map: dict) -> list[dict]:
    if type(refs) is not list or not 1 <= len(refs) <= 30:
        _invalid("invalid_source_region", "Each question needs 1 to 30 explicit source regions")
    copied = []
    for ref in refs:
        if type(ref) is not dict or set(ref) != {"source_id", "bbox"}:
            _invalid("invalid_source_region", "A source region has unsupported fields")
        source_id = ref["source_id"]
        source = source_map.get(source_id) if type(source_id) is str else None
        box = ref["bbox"]
        if (source is None or type(box) is not list or len(box) != 4 or
                any(type(coord) is not int for coord in box) or
                not 0 <= box[0] < box[2] <= source["width"] or
                not 0 <= box[1] < box[3] <= source["height"]):
            _invalid("invalid_source_region", "Source regions must use known-image integer coordinates")
        copied.append({"source_id": source_id, "bbox": list(box)})
    return copied


def _validate_proposal(proposal) -> dict:
    if type(proposal) is not dict or set(proposal) != {"printed_text", "missing_fields", "nodes", "answer"}:
        _invalid("invalid_draft", "Material draft fields are closed")
    printed_text = proposal["printed_text"]
    if printed_text is not None and (type(printed_text) is not str or len(printed_text) > 20_000 or "\x00" in printed_text):
        _invalid("invalid_draft", "Printed text must be bounded text or null")
    missing = proposal["missing_fields"]
    if (type(missing) is not list or len(missing) > 30 or
            any(type(item) is not str or len(item) > 200 for item in missing)):
        _invalid("invalid_draft", "Missing fields must be an explicit bounded list")
    if not printed_text and "printed_text" not in missing:
        _invalid("unknown_text_unmarked", "Unknown printed text must be listed in missing_fields")

    nodes = proposal["nodes"]
    if type(nodes) is not list or len(nodes) > 3:
        _invalid("invalid_draft", "At most three typed nodes are supported per question")
    for node in nodes:
        if type(node) is not dict or set(node) != {"kind", "data"}:
            _invalid("invalid_draft", "Node fields are closed")
        kind, data = node["kind"], node["data"]
        if type(kind) is not str or kind not in NODE_FIELDS or type(data) is not dict or set(data) - NODE_FIELDS[kind]:
            _invalid("invalid_draft", "Node kind or fields are unsupported")
        for value in data.values():
            if type(value) is not str or len(value) > 20_000 or "\x00" in value:
                _invalid("invalid_draft", "Node content must be bounded text")
        name_field = "definition" if kind == "knowledge" else "name"
        if not data.get(name_field, "").strip():
            _invalid("invalid_draft", "Knowledge, method and question type need an explicit name")

    answer = proposal["answer"]
    if answer is not None:
        if type(answer) is not dict or set(answer) != {"body", "formulas", "basis"}:
            _invalid("invalid_draft", "Answer fields are closed")
        for key, limit in (("body", 20_000), ("basis", 4_000)):
            value = answer[key]
            if type(value) is not str or not value.strip() or len(value) > limit or "\x00" in value:
                _invalid("invalid_draft", "Answer text and basis must be explicit and bounded")
        formulas = answer["formulas"]
        if type(formulas) is not list or len(formulas) > 20:
            _invalid("invalid_draft", "Answer formulas must be an explicit bounded list")
        try:
            for formula in formulas:
                validate_math(formula)
        except (ExportError, TypeError, ValueError, RecursionError) as exc:
            raise WorkflowError("invalid_formula", "Answer formula does not match the pure print contract") from exc
    return proposal


def _draft_records(question_id: str, draft, source_map: dict) -> tuple[list[dict], dict]:
    if (type(draft) is not dict or set(draft) != {"schema_version", "proposal", "sources", "original_number"}
            or draft["schema_version"] != "swb.material-draft.v1"):
        _invalid("invalid_draft", "Expected an explicit swb.material-draft.v1")
    original_number = draft["original_number"]
    if type(original_number) is not str or len(original_number) > 80:
        _invalid("invalid_draft", "Original number must be bounded text")
    refs = _source_refs(draft["sources"], source_map)
    proposal = _validate_proposal(draft["proposal"])
    question_record_id = f"{question_id}.question"
    rows = [{"id": question_record_id, "kind": "question", "data": {
        "printed_text": proposal["printed_text"], "original_number": original_number, "sources": refs,
    }}]
    nodes = {}
    for index, node in enumerate(proposal["nodes"]):
        node_id = f"{question_id}.node-{index}"
        link_id = f"{question_id}.link-{index}"
        kind = node["kind"]
        nodes[node_id] = kind
        rows.append({"id": node_id, "kind": kind, "data": {**deepcopy(node["data"]), "sources": deepcopy(refs)}})
        rows.append({"id": link_id, "kind": "link", "data": {
            "question": question_record_id,
            "node": node_id,
            "role": {"knowledge": "applies", "method": "primary", "question_type": "belongs"}[kind],
        }})
    if proposal["answer"] is not None:
        rows.append({"id": f"{question_id}.answer", "kind": "answer",
                     "data": {"question": question_record_id, **deepcopy(proposal["answer"])}})
    return rows, {"record_id": question_record_id, "sources": refs, "nodes": nodes}


def _asset_key(value) -> tuple[str, str]:
    if type(value) is not str or not value or "\\" in value or ":" in value:
        _invalid("invalid_asset_key", "Asset keys must be local relative POSIX paths")
    path = PurePosixPath(value)
    if (path.is_absolute() or ".." in path.parts or str(path) != value or
            any(part in {"", "."} for part in value.split("/")) or path.suffix not in ASSET_MEDIA):
        _invalid("invalid_asset_key", "Asset keys must be canonical relative PNG, SVG or PDF paths")
    return path.suffix, ASSET_MEDIA[path.suffix]


def _read_asset(asset_root: Path, key: str) -> bytes:
    try:
        path = resolve_under(asset_root, key)
        if not stat.S_ISREG(path.stat().st_mode):
            _invalid("invalid_asset", "Diagram resources must be regular files")
        with path.open("rb") as stream:
            raw = stream.read(MAX_ASSET_BYTES + 1)
    except WorkflowError:
        raise
    except OSError as exc:
        raise WorkflowError("invalid_asset", "Could not read a local diagram resource") from exc
    if not 1 <= len(raw) <= MAX_ASSET_BYTES:
        _invalid("asset_size", "Each diagram resource must be at most 512 KiB")
    return raw


def _validate_png(raw: bytes) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw), formats=("PNG",)) as image:
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1 or image.width * image.height > 4_000_000:
                    _invalid("invalid_png", "Diagram PNG must be a single frame of at most four million pixels")
                image.verify()
            with Image.open(io.BytesIO(raw), formats=("PNG",)) as image:
                image.load()
    except WorkflowError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise WorkflowError("invalid_png", "Diagram PNG cannot be fully decoded") from exc


def _validate_svg(raw: bytes) -> None:
    try:
        source = raw.decode("utf-8-sig")
        upper = source.upper()
        if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
            _invalid("unsafe_vector", "SVG declarations and entities are unsupported")
        tree = ET.fromstring(source)
        if tree.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
            _invalid("unsafe_vector", "Vector resource is not an SVG document")
        for element in tree.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag in _SVG_FORBIDDEN:
                _invalid("unsafe_vector", "SVG active and external elements are unsupported")
            for name, value in element.attrib.items():
                lowered_name, lowered_value = name.rsplit("}", 1)[-1].lower(), value.lower()
                if (lowered_name.startswith("on") or "href" in lowered_name or "url(" in lowered_value or
                        "javascript:" in lowered_value or "@import" in lowered_value):
                    _invalid("unsafe_vector", "SVG events and external resource references are unsupported")
    except WorkflowError:
        raise
    except (UnicodeError, ET.ParseError, ValueError) as exc:
        raise WorkflowError("unsafe_vector", "Vector SVG cannot be safely parsed") from exc


def _validate_pdf(raw: bytes) -> None:
    if not raw.startswith(b"%PDF-") or not raw.rstrip().endswith(b"%%EOF"):
        _invalid("unsafe_vector", "Vector PDF must have an explicit local PDF header and end marker")


def _read_typed_asset(root: Path, key: str, expected_suffix: str) -> tuple[bytes, str]:
    suffix, media_type = _asset_key(key)
    if suffix != expected_suffix:
        _invalid("invalid_asset_type", "PNG and paired vector keys must have matching file types")
    raw = _read_asset(root, key)
    if suffix == ".png":
        _validate_png(raw)
    elif suffix == ".svg":
        _validate_svg(raw)
    else:
        _validate_pdf(raw)
    return raw, media_type


def _diagram_record(diagram, question_map, asset_root: Path | None, assets: dict,
                    source_placements: set) -> dict:
    expected = {"id", "question", "placement", "png_key", "vector_key", "source", "alt", "conditions",
                "width_points", "min_label_points", "independent_safe", "basis"}
    if type(diagram) is not dict or set(diagram) != expected:
        _invalid("invalid_diagram", "Diagram fields are closed and explicit")
    diagram_id = _local_id(diagram["id"], "diagram id")
    question_id = diagram["question"]
    if type(question_id) is not str or question_id not in question_map:
        _invalid("invalid_diagram", "Diagram must reference a question in this content batch")
    placement = diagram["placement"]
    if type(placement) is not str or placement not in {"question", "answer"}:
        _invalid("invalid_diagram", "Diagram placement must be question or answer")
    placement_key = (question_id, placement)
    if placement_key in source_placements:
        _invalid("duplicate_diagram_placement", "Only one diagram per question placement is supported")
    source_placements.add(placement_key)
    question = question_map[question_id]
    source = diagram["source"]
    if type(source) is not dict or set(source) != {"source_id", "bbox"} or source not in question["sources"]:
        _invalid("diagram_source_mismatch", "Diagram source must be one of its question's exact source regions")

    _text(diagram["alt"], 2_000, "Diagram alt text")
    _text(diagram["basis"], 4_000, "Diagram basis")
    conditions = diagram["conditions"]
    if (type(conditions) is not list or not 1 <= len(conditions) <= 30 or
            any(type(value) is not str or not value.strip() or len(value) > 1_000 or "\x00" in value for value in conditions)):
        _invalid("invalid_diagram", "Diagram needs 1 to 30 bounded explicit conditions")
    width = diagram["width_points"]
    min_label = diagram["min_label_points"]
    if (type(width) not in (int, float) or not math.isfinite(width) or not 1 <= width <= 490 or
            type(min_label) not in (int, float) or not math.isfinite(min_label) or not 9 <= min_label <= 40 or
            type(diagram["independent_safe"]) is not bool):
        _invalid("invalid_diagram", "Diagram size, label size and independent flag are invalid")
    if placement == "question" and diagram["independent_safe"] is not True:
        _invalid("independent_hint", "Question diagrams must be explicitly safe for independent practice")
    if asset_root is None:
        _invalid("missing_asset_root", "An asset root is required for diagram content")

    for key_name, expected_suffix in (("png_key", ".png"), ("vector_key", None)):
        key = diagram[key_name]
        suffix, _ = _asset_key(key)
        if key_name == "vector_key" and suffix not in {".pdf", ".svg"}:
            _invalid("invalid_asset_type", "A vector key must refer to PDF or SVG")
        if expected_suffix is not None and suffix != expected_suffix:
            _invalid("invalid_asset_type", "A PNG key must refer to PNG")
        expected_type = suffix
        raw, media_type = _read_typed_asset(asset_root, key, expected_type)
        previous = assets.get(key)
        if previous is not None and previous["raw"] != raw:
            _invalid("asset_key_conflict", "A repeated asset key resolved to different bytes")
        if previous is None:
            assets[key] = {"raw": raw, "media_type": media_type}

    png_key, vector_key = diagram["png_key"], diagram["vector_key"]
    if (png_key == vector_key or assets[png_key]["media_type"] != "image/png" or
            assets[vector_key]["media_type"] not in {"application/pdf", "image/svg+xml"}):
        _invalid("invalid_asset_type", "Each diagram needs a PNG and a distinct paired PDF or SVG")
    return {"id": diagram_id, "kind": "diagram", "data": {
        "question": question["record_id"], "placement": placement,
        "png_asset": png_key, "vector_asset": vector_key, "source": deepcopy(source),
        "alt": diagram["alt"], "conditions": list(conditions),
        "width_points": width, "min_label_points": min_label,
        "independent_safe": diagram["independent_safe"], "basis": diagram["basis"],
    }}


def produce(content, sources, asset_root) -> dict:
    """Produce namespaced question/node/link/answer records plus verified diagram assets."""
    _bounded_json(content)
    _bounded_json(sources)
    if type(content) is not dict or set(content) != {"schema_version", "batch_id", "questions", "diagrams"}:
        _invalid("invalid_content", "Content batch fields are closed")
    if content["schema_version"] != CONTENT_SCHEMA:
        _invalid("invalid_content", "Unsupported Workbench content schema")
    source_map = _validate_sources(sources)
    if type(content["batch_id"]) is not str or content["batch_id"] != sources["batch_id"]:
        _invalid("batch_mismatch", "Content and source manifest batch IDs must match")

    questions = content["questions"]
    diagrams = content["diagrams"]
    if type(questions) is not list or not 1 <= len(questions) <= 100 or type(diagrams) is not list or len(diagrams) > 200:
        _invalid("invalid_content", "Question and diagram counts exceed supported bounds")

    rows = []
    question_map = {}
    input_ids = set()
    record_ids = set()
    for question in questions:
        if type(question) is not dict or set(question) != {"id", "draft"}:
            _invalid("invalid_question", "Each question needs exactly id and draft")
        question_id = _local_id(question["id"], "question id")
        if question_id in input_ids:
            _invalid("duplicate_identity", "Question and diagram IDs must be unique in the batch")
        input_ids.add(question_id)
        question_rows, question_info = _draft_records(question_id, question["draft"], source_map)
        rows.extend(question_rows)
        question_map[question_id] = question_info

    asset_root_path = root_path(asset_root) if diagrams else None
    assets = {}
    placements = set()
    for diagram in diagrams:
        if type(diagram) is not dict or "id" not in diagram:
            _invalid("invalid_diagram", "Each diagram needs a unique local ID")
        diagram_id = _local_id(diagram["id"], "diagram id")
        if diagram_id in input_ids:
            _invalid("duplicate_identity", "Question and diagram IDs must be unique in the batch")
        input_ids.add(diagram_id)
        rows.append(_diagram_record(diagram, question_map, asset_root_path, assets, placements))

    for row in rows:
        identity = _local_id(row["id"], "record id")
        if identity in record_ids:
            _invalid("duplicate_identity", "Generated record IDs must be unique")
        record_ids.add(identity)
    if len(rows) > MAX_RECORDS:
        _invalid("record_limit", "A companion package may contain at most 300 records")
    if len(assets) > 32:
        _invalid("asset_limit", "A companion package may contain at most 32 distinct assets")

    asset_records = {
        key: {"sha256": digest(value["raw"]), "media_type": value["media_type"],
              "base64": base64.b64encode(value["raw"]).decode("ascii")}
        for key, value in assets.items()
    }
    result = {"schema_version": OUTPUT_SCHEMA, "records": rows, "assets": asset_records}
    try:
        raw = canonical(result)
    except (TypeError, ValueError, RecursionError) as exc:
        raise WorkflowError("invalid_content", "Companion output is not finite canonical JSON") from exc
    if len(raw) > MAX_OUTPUT_BYTES:
        _invalid("output_too_large", "Complete companion output exceeds 1 MiB")
    return result


def main() -> dict:
    parser = WorkflowArgumentParser(description=__doc__)
    parser.add_argument("--content", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    content = read_json(args.content, max_bytes=MAX_INPUT_BYTES)
    sources = read_json(args.sources, max_bytes=MAX_INPUT_BYTES)
    value = produce(content, sources, args.asset_root)
    raw = canonical(value)
    parent = args.output.parent
    try:
        assert_no_symlinks(parent)
        if not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) != 0o700:
            _invalid("unsafe_output_root", "Output directory must already exist with mode 0700")
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except WorkflowError:
        raise
    except OSError as exc:
        raise WorkflowError("output_rejected", "Could not create a private exclusive output file") from exc
    return {"sha256": digest(raw), "record_count": len(value["records"]),
            "asset_count": len(value["assets"]), "database_opened": False, "review_state": "draft"}


if __name__ == "__main__":
    raise SystemExit(cli_result(main))
