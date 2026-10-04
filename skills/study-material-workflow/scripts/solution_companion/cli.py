"""Explicit offline companion render, status, verify and draft bundle commands."""
from __future__ import annotations

from pathlib import Path
import platform
import re
import sys
import uuid

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow_common import (
    WorkflowArgumentParser, WorkflowError, cli_result, ensure_output_outside,
    fail, read_json, root_path, write_json,
)
from run_state import environment_records, file_record, run_lock
from solution_companion.model import asset_records, code_records, validate_content


_PENDING = ["content_review", "math_review", "all_page_visual_review",
            "word_client_pc", "word_client_macos", "family_approval"]


def _environment():
    return {"python": platform.python_version(), "dependencies": environment_records()}


def _inputs(args, content, config):
    records = {name: file_record(getattr(args, name)) for name in ("content", "sources", "font_config")}
    for key in ("regular_source", "bold_source", "math_source"):
        records[key] = file_record(config[key])
    for asset in content["assets"]:
        from workflow_common import resolve_under
        records["asset:" + asset["storage_key"]] = file_record(resolve_under(args.asset_root, asset["storage_key"]))
    return records


def _load_run(path):
    state = read_json(path)
    expected = {"schema_version", "batch_id", "stage", "inputs", "source_root", "asset_root",
                "environment", "tool_hashes", "versions", "active_version", "pending"}
    if (type(state) is not dict or set(state) != expected or
            state["schema_version"] != "swf.solution-run.v1" or
            state["stage"] != "machine_verified" or type(state["inputs"]) is not dict or
            type(state["versions"]) is not list or state["active_version"] not in state["versions"] or
            state["pending"] != _PENDING):
        fail("invalid_run", "Expected a saved companion run; existing pointers are not overwritten")
    versions = state["versions"]
    parent = Path(path).resolve().parent / "versions"
    if (any(type(v) is not str for v in versions) or len(set(versions)) != len(versions) or
            any(not Path(v).is_absolute() or Path(v).parent != parent or
                not re.fullmatch(r"[0-9a-f]{24}", Path(v).name) for v in versions)):
        fail("invalid_run", "Saved versions must name distinct local immutable directories")
    return state


def render(args):
    from solution_companion.render import render_companion
    from solution_companion.verify import verify_companion
    root = root_path(args.output_root, must_exist=False)
    ensure_output_outside(args.source_root, root)
    if root_path(args.source_root).is_relative_to(root):
        fail("source_output_overlap", "Original sources and output roots must not overlap")
    if args.asset_root:
        assets = root_path(args.asset_root)
        if root.is_relative_to(assets) or assets.is_relative_to(root):
            fail("asset_output_overlap", "Resource and output roots must not overlap")
    before = {name: file_record(getattr(args, name)) for name in ("content", "sources", "font_config")}
    content, sources, config = read_json(args.content), read_json(args.sources), read_json(args.font_config)
    validate_content(content, sources)
    asset_records(content, sources, args.source_root, args.asset_root)
    inputs = _inputs(args, content, config)
    if any(inputs[name] != record for name, record in before.items()):
        fail("stale_input", "Input changed while loading; use stable input files")
    with run_lock(root):
        old = _load_run(root / "run.json") if (root / "run.json").exists() else None
        if old and old["batch_id"] != content["batch_id"]:
            fail("run_conflict", "Use a new run root for another batch")
        result = render_companion(content, sources, args.source_root, config, root / "versions", args.asset_root)
        verification = verify_companion(result["directory"], source_root=args.source_root)
        # Recheck external inputs after rendering, before advancing the success pointer.
        if inputs != _inputs(args, content, config):
            fail("stale_input", "An input changed during render; successful pointer was retained")
        versions = list(old["versions"]) if old else []
        active = str(Path(result["directory"]).resolve())
        if active not in versions:
            versions.append(active)
        state = {"schema_version": "swf.solution-run.v1", "batch_id": content["batch_id"],
                 "stage": "machine_verified", "inputs": inputs,
                 "source_root": str(root_path(args.source_root)),
                 "asset_root": str(root_path(args.asset_root)) if args.asset_root else None,
                 "environment": _environment(), "tool_hashes": code_records(),
                 "versions": versions, "active_version": active, "pending": list(_PENDING)}
        write_json(root / "run.json", state, replace=True)
    return {**result, "run": str(root / "run.json"), "stage": state["stage"],
            "word_client": verification["word_client"], "pending": state["pending"]}


def status(args):
    from solution_companion.verify import verify_companion
    path = Path(args.run)
    with run_lock(path.parent):
        state = _load_run(path)
        changed = []
        for name, record in state["inputs"].items():
            if type(record) is not dict or set(record) != {"path", "sha256"}:
                fail("invalid_run", "Input records must name exact file bytes")
            try:
                if file_record(record["path"]) != record:
                    changed.append(name)
            except (OSError, ValueError):
                changed.append(name)
        if state["tool_hashes"] != code_records():
            changed.append("tools")
        if state["environment"] != _environment():
            changed.append("environment")
        if changed:
            fail("stale_run", "Changed companion dependencies: " + ", ".join(changed))
        source_root = args.source_root or state["source_root"]
        report = verify_companion(state["active_version"], source_root=source_root)
    return {**report, "stage": state["stage"], "pending": state["pending"], "family_approved": False}


def main(argv=None):
    parser = WorkflowArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    item = commands.add_parser("render")
    for name in ("content", "sources", "source-root", "font-config", "output-root"):
        item.add_argument("--" + name, required=True)
    item.add_argument("--asset-root")
    item = commands.add_parser("status")
    item.add_argument("--run", required=True); item.add_argument("--source-root")
    item = commands.add_parser("verify")
    item.add_argument("--version", required=True); item.add_argument("--source-root")
    item = commands.add_parser("bundle")
    item.add_argument("--version", required=True); item.add_argument("--output", required=True)
    item.add_argument("--review")
    args = parser.parse_args(argv)
    try:
        if args.command == "render":
            return render(args)
        if args.command == "status":
            return status(args)
        if args.command == "verify":
            from solution_companion.verify import verify_companion
            return verify_companion(args.version, source_root=args.source_root)
        from solution_companion.bundle import bundle_companion
        return bundle_companion(args.version, args.output, read_json(args.review) if args.review else None)
    except (WorkflowError, OSError, ValueError, TypeError, KeyError) as exc:
        if args.command == "render":
            try:
                ensure_output_outside(args.source_root, args.output_root)
                root = Path(args.output_root)
                if root_path(args.source_root).is_relative_to(root.resolve()):
                    raise ValueError("overlapping root")
                if args.asset_root:
                    asset_root = root_path(args.asset_root)
                    if root.resolve().is_relative_to(asset_root) or asset_root.is_relative_to(root.resolve()):
                        raise ValueError("overlapping asset root")
                failure = {"schema_version": "swf.solution-failure.v1", "stage": "render",
                           "code": getattr(exc, "code", "invalid_input"), "message": str(exc)}
                write_json(root / "failures" / (uuid.uuid4().hex + ".json"), failure)
            except (OSError, ValueError):
                pass
        raise


if __name__ == "__main__":
    raise SystemExit(cli_result(main))
