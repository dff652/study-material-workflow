"""Report local Python dependencies and readable font files without changing the host."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import sys

import workflow_common as common


_DEPENDENCIES = (
    "Pillow",
    "reportlab",
    "python-docx",
    "fonttools",
    "lxml",
    "PyMuPDF",
)
_FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}
_DEFAULT_FONT_ROOTS = (Path("/usr/share/fonts"), Path("/usr/local/share/fonts"))


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        common.fail("invalid_arguments", "Command-line arguments do not match the tool contract")


def _dependency_versions() -> tuple[dict[str, str | None], list[str]]:
    versions: dict[str, str | None] = {}
    missing: list[str] = []
    for name in _DEPENDENCIES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
            missing.append(f"dependency:{name}")
    return versions, missing


def _family_names(path: Path) -> list[dict[str, str]]:
    """Read font names from local files; malformed and unreadable fonts are skipped."""
    try:
        from fontTools.ttLib import TTCollection, TTFont, TTLibError
    except ImportError:
        return []

    result = []
    try:
        if path.suffix.lower() in {".ttc", ".otc"}:
            collection = TTCollection(path, lazy=True)
            fonts = collection.fonts
        else:
            collection = None
            fonts = [TTFont(path, lazy=True)]
        try:
            for index, font in enumerate(fonts):
                names = font["name"]
                family = names.getDebugName(1) or names.getDebugName(16) or path.stem
                style = names.getDebugName(2) or names.getDebugName(17) or "unknown"
                result.append({"family": family, "style": style, "path": str(path), "face_index": index})
        finally:
            for font in fonts:
                font.close()
            if collection is not None:
                collection.close()
    except (OSError, KeyError, ValueError, AssertionError, IndexError, TTLibError):
        return []
    return result


def _scan_root(path: Path) -> tuple[dict, list[dict]]:
    status = {"path": str(path), "readable": False, "code": None}
    found: list[dict] = []
    try:
        common.assert_no_symlinks(path)
        if not path.is_dir():
            status["code"] = "missing_font_root"
            return status, found
        if not os.access(path, os.R_OK | os.X_OK):
            status["code"] = "font_root_unreadable"
            return status, found
        status["readable"] = True
        pending = [path]
        while pending:
            directory = pending.pop()
            try:
                with os.scandir(directory) as items:
                    for item in items:
                        try:
                            if item.is_symlink():
                                continue
                            if item.is_dir(follow_symlinks=False):
                                pending.append(Path(item.path))
                            elif Path(item.name).suffix.lower() in _FONT_EXTENSIONS and item.is_file(follow_symlinks=False):
                                found.extend(_family_names(Path(item.path)))
                        except OSError:
                            continue
            except OSError:
                status["code"] = "font_subdirectory_unreadable"
    except common.WorkflowError as exc:
        status["code"] = exc.code
    return status, found


def check_environment(font_root=None) -> dict:
    """Return interpreter, installed package versions, and fonts discoverable in local roots."""
    dependencies, missing = _dependency_versions()
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        missing.append("renderer_tool:pdftoppm")
    roots = [Path(font_root)] if font_root is not None else [path for path in _DEFAULT_FONT_ROOTS if path.exists()]
    if not roots:
        roots = list(_DEFAULT_FONT_ROOTS)

    root_statuses = []
    fonts = []
    for root in roots:
        status, discovered = _scan_root(root)
        root_statuses.append(status)
        fonts.extend(discovered)
        if status["code"]:
            missing.append(f"font_root:{status['code']}")
    if not fonts:
        missing.append("font_files")
    fonts.sort(key=lambda item: (item["family"].casefold(), item["style"].casefold(), item["path"], item["face_index"]))

    return {
        "interpreter": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "dependencies": dependencies,
        "renderer_tools": {"pdftoppm": {"available": pdftoppm is not None, "path": pdftoppm}},
        "fonts": {"roots": root_statuses, "available": fonts, "missing": [item for item in missing if item.startswith("font_")]},
        "missing": missing,
    }


def _main(argv=None):
    def run():
        parser = _JsonArgumentParser(description=__doc__)
        parser.add_argument("--font-root")
        args = parser.parse_args(argv)
        return check_environment(args.font_root)

    return common.cli_result(run)


if __name__ == "__main__":
    raise SystemExit(_main())
