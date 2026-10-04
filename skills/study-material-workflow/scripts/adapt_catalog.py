"""Adapt a legacy JSON index into a source-linked draft catalog."""
from __future__ import annotations

import argparse
import re

import workflow_common as common
from collect_sources import validate_manifest


_RAW_FIELDS = {"book", "num", "group", "photo", "feature", "method", "tag", "tip", "aux"}
_CALC_NUMBER = re.compile(r"([1-9][0-9]*)(?:\(([1-9][0-9]*)\)(?:-([1-9][0-9]*))?)?\Z")
_GEOM_NUMBER = re.compile(r"([1-9][0-9]*)(?:\(([1-9][0-9]*)\)(?:-([1-9][0-9]*))?|\((左|右)\))?\Z")
_AUX_PREFIX = re.compile(r"([0-9]+)(?:\s+(.+))?\Z")
_SEPARATORS = {"/", "+"}


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        common.fail("invalid_arguments", "Command-line arguments do not match the tool contract")


def _invalid(code: str, message: str):
    common.fail(code, message)


def _text(value, field: str, *, allow_empty: bool = False) -> str:
    valid = type(value) is str and value == value.strip() and not any(ord(char) < 32 for char in value)
    if not valid or (not allow_empty and not value):
        _invalid("invalid_catalog_row", f"{field} must be {'empty or non-empty' if allow_empty else 'non-empty'} source text")
    return value


def _validate_profile(profile) -> dict:
    required = {
        "profile_id", "namespace", "classification_revision", "books",
        "photo_separator", "allow_sides", "groups", "aux_aliases",
    }
    if type(profile) is not dict or set(profile) != required:
        _invalid("invalid_catalog_profile", "Profile has an invalid field set")
    for field in ("profile_id", "namespace", "classification_revision"):
        value = profile[field]
        if (type(value) is not str or not value or value != value.strip() or
                any(ord(char) < 32 for char in value)):
            _invalid("invalid_catalog_profile", f"{field} must be non-empty text")
    books = profile["books"]
    if (type(books) is not list or not books or
            any(type(book) is not str or not book or book != book.strip() or any(ord(char) < 32 for char in book)
                for book in books) or
            len(set(books)) != len(books)):
        _invalid("invalid_catalog_profile", "books must be a non-empty list of unique names")
    separator = profile["photo_separator"]
    if type(separator) is not str or separator not in _SEPARATORS:
        _invalid("invalid_catalog_profile", "photo_separator must be slash or plus")
    if type(profile["allow_sides"]) is not bool:
        _invalid("invalid_catalog_profile", "allow_sides must be a boolean")
    groups = profile["groups"]
    if type(groups) is not dict or set(groups) != {str(number) for number in range(1, 7)}:
        _invalid("invalid_catalog_profile", "groups must explicitly define numeric groups 1 through 6")
    if any(type(name) is not str or not name or name != name.strip() or any(ord(char) < 32 for char in name)
           for name in groups.values()):
        _invalid("invalid_catalog_profile", "every group needs a non-empty name")
    aliases = profile["aux_aliases"]
    if type(aliases) is not dict:
        _invalid("invalid_catalog_profile", "aux_aliases must map exact names to numeric groups")
    for name, group_id in aliases.items():
        if (type(name) is not str or not name or name != name.strip() or any(ord(char) < 32 for char in name) or
                type(group_id) is not int or str(group_id) not in groups):
            _invalid("invalid_catalog_profile", "aux_aliases must map exact non-empty names to groups 1 through 6")
    return profile


def _parse_number(value: str, *, allow_sides: bool) -> tuple[int, int | None, int | None, str | None]:
    expression = _GEOM_NUMBER if allow_sides else _CALC_NUMBER
    match = expression.fullmatch(value)
    if match is None:
        _invalid("invalid_question_number", "Question number must use N, N(k), N(k)-m, or an enabled side form")
    root, child, subquestion = match.groups()[:3]
    side = match.groups()[3] if allow_sides else None
    return int(root), int(child) if child is not None else None, int(subquestion) if subquestion is not None else None, side


def _parent_number(parsed: tuple[int, int | None, int | None, str | None]) -> str | None:
    root, child, subquestion, side = parsed
    if subquestion is not None:
        return f"{root}({child})"
    if child is not None or side is not None:
        return str(root)
    return None


def _ancestors(parsed: tuple[int, int | None, int | None, str | None]) -> list[str]:
    root, child, subquestion, side = parsed
    result: list[str] = []
    if subquestion is not None:
        result.append(f"{root}({child})")
    if child is not None or side is not None:
        result.append(str(root))
    return result


def _number_key(value: str, *, allow_sides: bool) -> tuple:
    root, child, subquestion, side = _parse_number(value, allow_sides=allow_sides)
    if child is None and side is None:
        return root, 0, 0, 0
    if side is not None:
        return root, 1, 1 if side == "左" else 2, 0
    return root, 2, child or 0, subquestion or 0


def _question_id(batch_id: str, namespace: str, book: str, display_number: str) -> str:
    identity = common.canonical([batch_id, namespace, book, display_number])
    return "q_" + common.digest(identity)[:24]


def _method_id(namespace: str, group_id: int) -> str:
    return "m_" + common.digest(common.canonical([namespace, group_id]))[:24]


def _auxiliary_groups(aux: str, aliases: dict, groups: dict) -> tuple[list[int], list[str]]:
    if aux == "":
        return [], []
    if not aux.strip():
        _invalid("malformed_auxiliary_method", "aux must be empty or contain semicolon-separated references")
    methods: list[int] = []
    unknown: list[str] = []
    seen_methods: set[int] = set()
    for raw_segment in re.split(r"[;；]", aux):
        segment = raw_segment.strip()
        if not segment:
            _invalid("malformed_auxiliary_method", "aux contains an empty reference")
        match = _AUX_PREFIX.fullmatch(segment)
        if match is not None:
            if match.group(1).startswith("0"):
                _invalid("malformed_auxiliary_method", "Numeric auxiliary prefixes must not contain leading zeroes")
            group_id = int(match.group(1))
            if str(group_id) not in groups:
                _invalid("unknown_auxiliary_group", "Numeric auxiliary prefix is outside groups 1 through 6")
            label = match.group(2)
            if label:
                mapped = aliases.get(label)
                if mapped is None:
                    unknown.append(label)
                elif mapped != group_id:
                    _invalid("auxiliary_mapping_conflict", "Numeric auxiliary prefix conflicts with its explicit name mapping")
        else:
            group_id = aliases.get(segment)
            if group_id is None:
                unknown.append(segment)
                continue
        if group_id not in seen_methods:
            methods.append(group_id)
            seen_methods.add(group_id)
    return methods, list(dict.fromkeys(unknown))


def _validate_row(row, index: int, profile: dict) -> tuple[dict, tuple, list[str], list[str], list[int]]:
    if type(row) is not dict or set(row) != _RAW_FIELDS or any(type(key) is not str for key in row):
        _invalid("invalid_catalog_row", f"Row {index} must contain exactly the nine legacy fields")
    for field in ("book", "num", "photo", "feature", "method", "tag", "tip"):
        _text(row[field], field)
    _text(row["aux"], "aux", allow_empty=True)
    if row["book"] not in profile["books"]:
        _invalid("unknown_book", f"Row {index} book is outside the selected profile")
    group_id = row["group"]
    if type(group_id) is not int or str(group_id) not in profile["groups"]:
        _invalid("unknown_group", f"Row {index} group must be an integer from 1 through 6")

    parsed_number = _parse_number(row["num"], allow_sides=profile["allow_sides"])
    photo = row["photo"]
    separator = profile["photo_separator"]
    tokens = photo.split(separator)
    if any(re.fullmatch(r"[0-9]{6}", token) is None for token in tokens) or len(tokens) != len(set(tokens)):
        _invalid("invalid_photo_list", f"Row {index} photo must contain unique six-digit tokens")

    aux_ids, unknown_names = _auxiliary_groups(row["aux"], profile["aux_aliases"], profile["groups"])
    return dict(row), parsed_number, tokens, unknown_names, [group_id, *aux_ids]


def adapt_catalog(rows, manifest, profile) -> dict:
    """Convert the old JSON row array to a stable, source-linked draft catalog."""
    validate_manifest(manifest)
    profile = _validate_profile(profile)
    if type(rows) is not list or not rows:
        _invalid("invalid_catalog", "Legacy catalog must be a non-empty JSON array of rows")

    source_lookup: dict[tuple[str, str], dict] = {}
    for source in manifest["sources"]:
        identity = (source["book"], source["token"])
        if identity in source_lookup:
            _invalid("duplicate_manifest_source", "Source book and token lookup must be unique")
        source_lookup[identity] = source

    parsed: list[dict] = []
    seen_rows: set[tuple[str, str]] = set()
    node_kinds: dict[tuple[str, str], str] = {}
    parent_roots: set[tuple[str, int]] = set()

    for index, source_row in enumerate(rows):
        raw, number_parts, photo_tokens, unknown_names, method_ids = _validate_row(source_row, index, profile)
        identity = (raw["book"], raw["num"])
        if identity in seen_rows:
            _invalid("duplicate_question_number", f"Row {index} repeats a book and question number")
        seen_rows.add(identity)
        root, _, _, _ = number_parts
        parent_roots.add((raw["book"], root))
        refs = []
        for sequence, token in enumerate(photo_tokens, 1):
            source = source_lookup.get((raw["book"], token))
            if source is None:
                _invalid("missing_source", f"Row {index} references a photo without a matching book source")
            refs.append({
                "source_id": source["source_id"],
                "sequence": sequence,
                "granularity": "whole_image",
                "region": None,
            })
        node_kinds[identity] = "entry"
        for ancestor in _ancestors(number_parts):
            node_kinds.setdefault((raw["book"], ancestor), "parent")
        parsed.append({
            "raw": raw,
            "book": raw["book"],
            "number": raw["num"],
            "number_parts": number_parts,
            "photo_refs": refs,
            "unknown_auxiliary": unknown_names,
            "method_group_ids": method_ids,
        })

    books = {book: index for index, book in enumerate(profile["books"])}
    all_nodes = []
    for book, display_number in sorted(
        node_kinds,
        key=lambda identity: (books[identity[0]], *_number_key(identity[1], allow_sides=profile["allow_sides"])),
    ):
        node_id = _question_id(manifest["batch_id"], profile["namespace"], book, display_number)
        number_parts = _parse_number(display_number, allow_sides=profile["allow_sides"])
        parent_number = _parent_number(number_parts)
        parent_id = _question_id(manifest["batch_id"], profile["namespace"], book, parent_number) if parent_number else None
        all_nodes.append({
            "question_id": node_id,
            "parent_id": parent_id,
            "book": book,
            "display_number": display_number,
            "node_type": node_kinds[(book, display_number)],
        })

    entries = []
    warnings = []
    for item in parsed:
        raw = item["raw"]
        question_id = _question_id(manifest["batch_id"], profile["namespace"], item["book"], item["number"])
        parent_number = _parent_number(item["number_parts"])
        parent_id = _question_id(manifest["batch_id"], profile["namespace"], item["book"], parent_number) if parent_number else None
        method_groups = item["method_group_ids"]
        primary_id = _method_id(profile["namespace"], method_groups[0])
        auxiliary_ids = []
        for group_id in method_groups[1:]:
            method_id = _method_id(profile["namespace"], group_id)
            if method_id not in auxiliary_ids:
                auxiliary_ids.append(method_id)
        gaps = ["printed_text_missing", "exact_region_missing", "attempt_source_unknown"]
        for unknown in item["unknown_auxiliary"]:
            gaps.append("unknown_auxiliary_method")
            warnings.append({
                "code": "unknown_auxiliary_method",
                "question_id": question_id,
                "raw_value": unknown,
            })
        entries.append({
            "question_id": question_id,
            "parent_id": parent_id,
            "book": item["book"],
            "display_number": item["number"],
            "raw": raw,
            "photo_refs": item["photo_refs"],
            "primary_method_id": primary_id,
            "auxiliary_method_ids": auxiliary_ids,
            "gaps": list(dict.fromkeys(gaps)),
            "review_state": "draft",
        })

    expected_counts = manifest["expected_counts"]
    actual_counts = {"parent_questions": len(parent_roots), "entries": len(entries)}
    for name, actual in actual_counts.items():
        if name in expected_counts and expected_counts[name] != actual:
            _invalid("catalog_count_mismatch", f"Catalog {name} count does not match expected_counts.{name}")

    return {
        "schema_version": "swf.catalog.v1",
        "batch_id": manifest["batch_id"],
        "profile_id": profile["profile_id"],
        "namespace": profile["namespace"],
        "classification_revision": profile["classification_revision"],
        "source_manifest_sha256": common.digest(common.canonical(manifest)),
        "counts": {
            "sources": len(manifest["sources"]),
            "parent_questions": len(parent_roots),
            "entries": len(entries),
            "question_nodes": len(all_nodes),
        },
        "entries": entries,
        "nodes": all_nodes,
        "warnings": warnings,
    }


def _main(argv=None):
    def run():
        parser = _JsonArgumentParser(description=__doc__)
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--profile", required=True)
        parser.add_argument("--catalog", required=True)
        parser.add_argument("--output", required=True)
        args = parser.parse_args(argv)
        manifest = common.read_json(args.manifest)
        profile = common.read_json(args.profile)
        rows = common.read_json(args.catalog)
        catalog = adapt_catalog(rows, manifest, profile)
        common.write_json(args.output, catalog)
        return catalog
    return common.cli_result(run)


if __name__ == "__main__":
    raise SystemExit(_main())
