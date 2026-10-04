"""Versioned five-document envelope; human review stays separate from rendering."""
from workflow_common import canonical, digest, fail, WorkflowError
from print_backend.contracts import PURPOSES, document_from_dict, resolve_formula_image,ExportError


def packet_digest(packet):
    return digest(canonical({k: v for k, v in packet.items() if k != "review"}))


def validate_packet(packet, sources=None, catalog=None):
    required = {"schema_version", "batch_id", "sources_sha256", "catalog_sha256", "documents", "omitted_purposes"}
    if not isinstance(packet, dict) or not required <= set(packet) or set(packet) - required - {"review"}:
        fail("invalid_packet", "Packet fields must be explicit")
    if packet["schema_version"] != "swf.packet.v1" or not isinstance(packet["batch_id"], str) or not packet["batch_id"].strip():
        fail("invalid_packet", "Unsupported packet schema or empty batch")
    for key in ("sources_sha256", "catalog_sha256"):
        value = packet[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            fail("invalid_packet", "Source and catalog hashes must be explicit SHA-256")
    for value, key in ((sources, "sources_sha256"), (catalog, "catalog_sha256")):
        if value is not None and (value.get("batch_id") != packet["batch_id"] or digest(canonical(value)) != packet[key]):
            fail("stale_input", "Packet does not match this batch's current input")
    if not isinstance(packet["documents"], list) or not 1 <= len(packet["documents"]) <= 5:
        fail("invalid_packet", "Packet needs one to five explicit documents")
    try:
        documents = [document_from_dict(value) for value in packet["documents"]]
    except ExportError as exc:
        raise WorkflowError(exc.code,str(exc)) from exc
    purposes = [document.purpose for document in documents]
    ids = [document.document_id for document in documents]
    omitted = packet["omitted_purposes"]
    if (not isinstance(omitted, list) or any(not isinstance(v, str) for v in omitted) or
        len(set(omitted)) != len(omitted) or len(set(purposes)) != len(purposes) or len(set(ids)) != len(ids) or
        set(purposes) & set(omitted) or set(purposes) | set(omitted) != PURPOSES):
        fail("invalid_purposes", "Included and omitted purposes must partition the five uses")
    for document in documents:
        if document.source.sha256 != packet["catalog_sha256"]:
            fail("stale_source", "Document must name the exact catalog input hash")
    if "review" in packet:
        validate_review(packet["review"], packet)
    if any(d.source.state == "accepted" for d in documents):
        review = packet.get("review", {})
        if any(review.get(k, {}).get("status") != "pass" for k in ("content", "math")):
            fail("missing_review", "Accepted content needs matching content and math review")
    return documents


def asset_records(packet, asset_root):
    records = {}
    for document in validate_packet(packet):
        for page in document.pages:
            for block in page:
                if block.kind in {"diagram", "formula_image"}:
                    try:
                        path = resolve_formula_image(block.content, asset_root)
                    except ExportError as exc:
                        raise WorkflowError(exc.code,str(exc)) from exc
                    key = block.content["storage_key"]
                    record = {"sha256": digest(path.read_bytes()), "size": path.stat().st_size}
                    if key in records and records[key] != record:
                        fail("asset_conflict", "A resource key refers to inconsistent bytes")
                    records[key] = record
    return records


def validate_review(review, packet, *, recipe_sha256=None, require_verified=False):
    names = {"content", "math", "independent", "pdf_visual", "word_client"}
    if (not isinstance(review, dict) or set(review) - names - {"packet_sha256", "recipe_sha256"} or
        review.get("packet_sha256") != packet_digest(packet)):
        fail("stale_review", "Review must name the exact packet content hash")
    for name in names & set(review):
        item = review[name]
        if (not isinstance(item, dict) or set(item) != {"status", "reviewer", "notes"} or
            item["status"] not in {"pass", "fail", "not_tested", "not_applicable"} or
            (item["reviewer"] is not None and not isinstance(item["reviewer"], str)) or not isinstance(item["notes"], str)):
            fail("invalid_review", "Review fields must record status, person and notes")
        if item["status"] == "pass" and (not isinstance(item["reviewer"],str) or not item["reviewer"].strip()):
            fail("invalid_review", "Pass needs an actual reviewer")
        if item["status"] == "not_applicable" and not item["notes"].strip():
            fail("invalid_review", "Not-applicable needs a scope explanation")
    if require_verified:
        if recipe_sha256 is None or review.get("recipe_sha256") != recipe_sha256:
            fail("stale_review", "Visual review must match the exact render recipe")
        for name in ("content", "math", "pdf_visual"):
            if review.get(name, {}).get("status") != "pass":
                fail("missing_review", "Content, math and all-page visual review are required")
        has_independent = any(d["purpose"] == "independent_practice" for d in packet["documents"])
        if review.get("independent", {}).get("status") != ("pass" if has_independent else "not_applicable"):
            fail("missing_review", "Independent-use semantic review must match the selected scope")
        word = review.get("word_client", {})
        if word.get("status") not in {"pass", "not_tested"} or not word.get("notes", "").strip():
            fail("missing_review", "Word client status and practical limits must be recorded")
    return review
