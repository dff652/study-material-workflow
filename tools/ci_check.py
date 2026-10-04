#!/usr/bin/env python3
"""Run strict, portable repository checks and create anonymous CI evidence."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPOSITORY / "skills" / "study-material-workflow" / "scripts"
TESTS_DIR = REPOSITORY / "tests"
DEFAULT_FONT_CONFIG = (
    REPOSITORY / "skills" / "study-material-workflow" / "assets" / "font-config.example.json"
)
sys.path.insert(0, str(SCRIPT_DIR))

import check_environment  # noqa: E402
import workflow_common  # noqa: E402


class CIError(ValueError):
    """A safe refusal before creating CI evidence."""


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY / path


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise CIError("Path contains a symbolic link")


def prepare_output_root(value: str | Path) -> Path:
    """Create a fresh output directory or accept an existing empty real directory."""
    path = Path(os.path.abspath(_repo_path(value)))
    _reject_symlink_components(path)
    if path.exists():
        if not path.is_dir():
            raise CIError("Output root exists and is not a directory")
        if next(path.iterdir(), None) is not None:
            raise CIError("Output root must be nonexistent or empty")
    else:
        path.mkdir(parents=True, mode=0o700)
    return path


def strict_tests_accepted(result: unittest.TestResult) -> bool:
    """Require a nonempty suite where every test has an ordinary passing result."""
    return (
        result.testsRun > 0
        and result.wasSuccessful()
        and not result.skipped
        and not result.expectedFailures
        and not result.unexpectedSuccesses
    )


def _test_counts(result: unittest.TestResult, discovery_error: bool = False) -> dict[str, int]:
    expected_failures = len(result.expectedFailures)
    unexpected_successes = len(result.unexpectedSuccesses)
    failures = len(result.failures)
    errors = len(result.errors) + int(discovery_error)
    skipped = len(result.skipped)
    return {
        "discovered": result.testsRun,
        "passed": max(
            0,
            result.testsRun - failures - errors - skipped - expected_failures - unexpected_successes,
        ),
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "expected_failures": expected_failures,
        "unexpected_successes": unexpected_successes,
    }


def _write_json_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    path.chmod(0o600)


def _write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)
    path.chmod(0o600)


def _requirements() -> dict[str, str]:
    pins: dict[str, str] = {}
    pin_pattern = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+-]*)$")
    for raw_line in (REPOSITORY / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = pin_pattern.fullmatch(line)
        if not match:
            raise ValueError("requirements.txt must contain exact direct dependency pins")
        name, version = match.groups()
        key = name.casefold().replace("_", "-").replace(".", "-")
        if key in pins:
            raise ValueError("requirements.txt contains a duplicate dependency")
        pins[key] = version
    if not pins:
        raise ValueError("requirements.txt contains no pinned dependencies")
    return pins


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPOSITORY), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", value) else None


def _font_family(path: Path, face_index: int) -> str:
    workflow_common.assert_no_symlinks(path)
    if not path.is_file():
        raise ValueError("A configured font file is missing")
    from fontTools.ttLib import TTFont

    font = TTFont(str(path), fontNumber=face_index, lazy=True)
    try:
        family = font["name"].getDebugName(1)
        if not family:
            raise ValueError("A configured font has no family name")
        return family
    finally:
        font.close()


def _font_config_path(value: str | None) -> Path:
    path = DEFAULT_FONT_CONFIG if value is None else _repo_path(value)
    return Path(os.path.abspath(path))


def _environment_preflight(font_config_path: Path) -> tuple[dict, list[str]]:
    raw = check_environment.check_environment()
    issues: list[str] = []
    dependencies = raw["dependencies"]
    try:
        pins = _requirements()
        installed = {
            name.casefold().replace("_", "-").replace(".", "-"): version
            for name, version in dependencies.items()
            if version is not None
        }
        if installed != pins:
            issues.append("dependency_pins_mismatch")
    except (OSError, ValueError):
        issues.append("requirements_not_exactly_pinned")

    python_version = tuple(sys.version_info[:2])
    if python_version != (3, 12):
        issues.append("python_3_12_required")
    if not raw["renderer_tools"]["pdftoppm"]["available"]:
        issues.append("pdftoppm_missing")
    elif raw["missing"]:
        issues.extend("environment_missing_requirement" for _ in raw["missing"])

    pdftoppm_version = None
    executable = raw["renderer_tools"]["pdftoppm"]["path"]
    if executable:
        try:
            result = subprocess.run(
                [executable, "-v"], capture_output=True, text=True, timeout=5, check=False
            )
            output = (result.stderr or result.stdout).strip().splitlines()
            if result.returncode != 0 or not output:
                issues.append("pdftoppm_unusable")
            else:
                pdftoppm_version = output[0][:160]
        except (OSError, subprocess.TimeoutExpired):
            issues.append("pdftoppm_unusable")

    font_evidence = {"status": "failed", "cjk_family": None, "math_family": None}
    try:
        workflow_common.assert_no_symlinks(font_config_path)
        config = json.loads(font_config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or set(config) != {
            "regular_source", "bold_source", "math_source", "face_index"
        }:
            raise ValueError("Invalid font config fields")
        face_index = config["face_index"]
        if type(face_index) is not int or face_index < 0:
            raise ValueError("Invalid CJK face index")

        font_paths = {}
        for role in ("regular", "bold", "math"):
            configured = config[f"{role}_source"]
            if not isinstance(configured, str) or not configured.strip():
                raise ValueError("Invalid font path")
            candidate = Path(configured)
            if not candidate.is_absolute():
                candidate = font_config_path.parent / candidate
            workflow_common.assert_no_symlinks(candidate)
            font_paths[role] = candidate.resolve(strict=True)

        regular_family = _font_family(font_paths["regular"], face_index)
        bold_family = _font_family(font_paths["bold"], face_index)
        math_family = _font_family(font_paths["math"], 0)
        if regular_family != "Noto Sans CJK SC" or bold_family != "Noto Sans CJK SC":
            raise ValueError("Configured CJK face must be Noto Sans CJK SC")
        if math_family != "DejaVu Serif":
            raise ValueError("Configured math font must be DejaVu Serif")
        font_evidence = {
            "status": "passed",
            "cjk_family": regular_family,
            "math_family": math_family,
            "face_index": face_index,
        }
    except Exception:
        issues.append("example_fonts_unavailable_or_invalid")

    evidence = {
        "status": "passed" if not issues else "failed",
        "interpreter": {
            "version": raw["interpreter"]["version"],
            "implementation": raw["interpreter"]["implementation"],
        },
        "dependencies": dependencies,
        "renderer_tools": {
            "pdftoppm": {
                "available": bool(executable),
                "version": pdftoppm_version,
            }
        },
        "font_preflight": font_evidence,
        "git_head": _git_head(),
    }
    return evidence, issues


def _run_tests() -> tuple[str, unittest.TestResult, str | None]:
    previous_cwd = Path.cwd()
    output = io.StringIO()
    result = unittest.TestResult()
    discovery_error = None
    try:
        os.chdir(REPOSITORY)
        suite = unittest.defaultTestLoader.discover(str(TESTS_DIR), pattern="test*.py")
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    except Exception:
        discovery_error = traceback.format_exc()
        output.write(discovery_error)
    finally:
        os.chdir(previous_cwd)
    return output.getvalue(), result, discovery_error


def _run_demo(output_root: Path, font_config_path: Path) -> dict:
    from make_demo import make_demo
    from verify_packet import verify_packet

    demo_root = output_root / "demo"
    first = make_demo(demo_root, font_config_path)
    replay = make_demo(demo_root, font_config_path)
    verified = verify_packet(first["directory"])
    run_inputs = workflow_common.read_json(demo_root / "run" / "inputs" / "sources.json")
    source_count = len(run_inputs["sources"])
    catalog = workflow_common.read_json(demo_root / "run" / "inputs" / "catalog.json")
    result = {
        "status": "passed",
        "recipe_sha256": first["recipe_sha256"],
        "sources": source_count,
        "documents": verified["documents"],
        "pdf_pages": verified["pdf_pages"],
        "verification": verified["status"],
        "replay_reused": bool(replay["reused"]),
        "catalog_counts": catalog["counts"],
        "synthetic_sources": True,
        "human_review": "not_tested",
        "word_client": verified["word_client"],
        "ocr": "not_tested",
        "learning_effect": "not_tested",
        "published": False,
    }
    if (
        not first["verification"]["status"] == "passed"
        or not replay["verification"]["status"] == "passed"
        or not verified["status"] == "passed"
        or first["reused"]
        or not replay["reused"]
        or source_count != 2
        or result["documents"] != 5
        or result["pdf_pages"] != 5
        or result["human_review"] != "not_tested"
        or result["word_client"] != "not_tested"
        or not result["synthetic_sources"]
        or result["published"]
    ):
        raise ValueError("Anonymous demo did not meet the expected machine-verification contract")
    return result


def run(output_root: Path, font_config_path: Path) -> int:
    failures: list[str] = []
    environment: dict = {"status": "failed", "git_head": _git_head()}
    try:
        environment, environment_issues = _environment_preflight(font_config_path)
        failures.extend(environment_issues)
    except Exception:
        failures.append("environment_preflight_failed")

    _write_json_new(output_root / "environment.json", environment)

    tests_log, test_result, discovery_error = _run_tests()
    test_counts = _test_counts(test_result, bool(discovery_error))
    if discovery_error:
        failures.append("test_discovery_failed")
    if not strict_tests_accepted(test_result):
        failures.append("strict_test_acceptance_failed")
    _write_text_new(output_root / "tests.log", tests_log or "No test output was produced.\n")

    demo: dict = {"status": "not_run"}
    if environment["status"] == "passed":
        try:
            demo = _run_demo(output_root, font_config_path)
        except Exception:
            demo = {"status": "failed"}
            failures.append("anonymous_demo_failed")
    else:
        failures.append("anonymous_demo_not_run_after_preflight_failure")

    summary = {
        "schema_version": "swf.ci-summary.v1",
        "status": "passed" if not failures else "failed",
        "git_head": environment.get("git_head"),
        "environment_status": environment.get("status", "failed"),
        "tests": test_counts,
        "demo": demo,
        "human_review": "not_tested",
        "word_client": "not_tested",
        "ocr": "not_tested",
        "learning_effect": "not_tested",
        "published": False,
        "failures": failures,
    }
    _write_json_new(output_root / "summary.json", summary)
    return 0 if summary["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, help="New or empty evidence directory")
    parser.add_argument("--font-config", help="Font config (default: repository example config)")
    args = parser.parse_args(argv)
    try:
        output_root = prepare_output_root(args.output_root)
        font_config_path = _font_config_path(args.font_config)
    except (CIError, OSError, ValueError) as exc:
        print(f"ci_check: {exc}", file=sys.stderr)
        return 2

    code = run(output_root, font_config_path)
    print(
        "CI validation passed" if code == 0 else "CI validation failed",
        f"(evidence: {output_root.relative_to(REPOSITORY) if output_root.is_relative_to(REPOSITORY) else output_root.name})",
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
