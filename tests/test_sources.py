from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "study-material-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import collect_sources
import workflow_common


def make_image(path: Path, fmt: str = "PNG", color=(20, 40, 60), size=(12, 8)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    raw = buffer.getvalue()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def selection(*items, batch_id="batch-synthetic", expected_counts=None):
    value = {"batch_id": batch_id, "files": list(items)}
    if expected_counts is not None:
        value["expected_counts"] = expected_counts
    return value


def item(path, book="J1", token="000001", page_order=None):
    return {"path": path, "book": book, "token": token, "page_order": page_order}


class CollectSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source_root = self.base / "source"
        self.source_root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def error_code(self, code, function, *args, **kwargs):
        with self.assertRaises(workflow_common.WorkflowError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_only_selected_jpeg_png_are_manifested_and_original_bytes_stay_unchanged(self):
        first = make_image(self.source_root / "page-a.jpg", "JPEG")
        second = make_image(self.source_root / "sub" / "page-b.png", "PNG", color=(90, 20, 10))
        ignored = make_image(self.source_root / "ignored.png", "PNG")
        hashes_before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in (self.source_root / "page-a.jpg", self.source_root / "sub" / "page-b.png", self.source_root / "ignored.png")}

        manifest = collect_sources.collect_sources(
            self.source_root,
            selection(item("page-a.jpg", token="000001", page_order=1),
                      item("sub/page-b.png", token="000002", page_order=None),
                      expected_counts={"sources": 2, "entries": 3}),
        )

        self.assertEqual(manifest["schema_version"], "swf.sources.v1")
        self.assertEqual([source["storage_key"] for source in manifest["sources"]], ["page-a.jpg", "sub/page-b.png"])
        self.assertEqual([source["format"] for source in manifest["sources"]], ["JPEG", "PNG"])
        self.assertEqual(manifest["sources"][1]["page_order"], None)
        self.assertEqual(manifest["sources"][0]["sha256"], hashlib.sha256(first).hexdigest())
        self.assertEqual(manifest["sources"][1]["sha256"], hashlib.sha256(second).hexdigest())
        self.assertTrue(collect_sources.validate_manifest(manifest))
        self.assertTrue(collect_sources.verify_sources(manifest, self.source_root))
        self.assertEqual(hashes_before["ignored.png"], hashlib.sha256(ignored).hexdigest())
        for name, before in hashes_before.items():
            path = self.source_root / name
            if not path.exists():
                path = self.source_root / "sub" / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_stable_ids_and_output_writes_are_idempotent_and_conflict_safe(self):
        original = make_image(self.source_root / "page.png")
        chosen = selection(item("page.png"))
        output = self.base / "prepared" / "sources.json"

        first = collect_sources.collect_sources(self.source_root, chosen, output)
        first_bytes = output.read_bytes()
        second = collect_sources.collect_sources(self.source_root, chosen, output)
        self.assertEqual(first, second)
        self.assertEqual(output.read_bytes(), first_bytes)
        self.assertEqual(hashlib.sha256(original).hexdigest(), first["sources"][0]["sha256"])

        make_image(self.source_root / "page.png", color=(80, 20, 10))
        self.error_code("output_conflict", collect_sources.collect_sources, self.source_root, chosen, output)

    def test_duplicate_paths_pairs_and_declared_counts_are_rejected(self):
        make_image(self.source_root / "page.png")
        make_image(self.source_root / "page-2.png", color=(10, 20, 30))
        self.error_code("duplicate_source_path", collect_sources.collect_sources, self.source_root,
                        selection(item("page.png"), item("page.png", token="000002")))
        self.error_code("duplicate_book_token", collect_sources.collect_sources, self.source_root,
                        selection(item("page.png"), item("page-2.png")))
        self.error_code("source_count_mismatch", collect_sources.collect_sources, self.source_root,
                        selection(item("page.png"), expected_counts={"sources": 2}))

    def test_path_escape_symlinks_and_source_output_overlap_are_rejected(self):
        make_image(self.source_root / "page.png")
        self.error_code("path_escape", collect_sources.collect_sources, self.source_root,
                        selection(item("../page.png")))
        link = self.source_root / "linked.png"
        link.symlink_to(self.source_root / "page.png")
        self.error_code("symlink_path", collect_sources.collect_sources, self.source_root,
                        selection(item("linked.png")))
        self.error_code("source_output_overlap", collect_sources.collect_sources, self.source_root,
                        selection(item("page.png")), self.source_root / "manifest.json")

    def test_corrupt_byte_limit_pixel_limit_and_modified_sources_fail_closed(self):
        (self.source_root / "corrupt.png").write_bytes(b"not an image")
        self.error_code("invalid_image", collect_sources.collect_sources, self.source_root,
                        selection(item("corrupt.png")))
        animated = io.BytesIO()
        first_frame = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
        second_frame = Image.new("RGBA", (4, 4), (0, 0, 255, 255))
        first_frame.save(animated, format="PNG", save_all=True, append_images=[second_frame], duration=100, loop=0)
        (self.source_root / "animated.png").write_bytes(animated.getvalue())
        self.error_code("unsupported_image", collect_sources.collect_sources, self.source_root,
                        selection(item("animated.png")))
        make_image(self.source_root / "large.png", size=(12, 8))
        self.error_code("source_too_large", collect_sources.collect_sources, self.source_root,
                        selection(item("large.png")), max_bytes=4)
        self.error_code("image_too_large", collect_sources.collect_sources, self.source_root,
                        selection(item("large.png")), max_pixels=20)

        manifest = collect_sources.collect_sources(self.source_root, selection(item("large.png")))
        make_image(self.source_root / "large.png", color=(1, 2, 3), size=(12, 8))
        self.error_code("source_hash_mismatch", collect_sources.verify_sources, manifest, self.source_root)

    def test_selection_file_is_read_as_json_and_cli_contract_emits_one_json_result(self):
        make_image(self.source_root / "page.png")
        selection_path = self.base / "selection.json"
        selection_path.write_text('{"batch_id":"batch-cli","files":[{"path":"page.png","book":"J1","token":"000001","page_order":null}]}', encoding="utf-8")
        output = self.base / "out" / "sources.json"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "collect_sources.py"), "--source-root", str(self.source_root),
             "--selection", str(selection_path), "--output", str(output)],
            cwd=SCRIPTS.parents[2], text=True, capture_output=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        cli_result = json.loads(completed.stdout)
        self.assertEqual(cli_result["batch_id"], "batch-cli")
        self.assertEqual(collect_sources.validate_manifest(workflow_common.read_json(output)), True)

        bad_args = subprocess.run(
            [sys.executable, str(SCRIPTS / "collect_sources.py"), "--source-root", str(self.source_root)],
            cwd=SCRIPTS.parents[2], text=True, capture_output=True, check=False,
        )
        self.assertEqual(bad_args.returncode, 2)
        self.assertEqual(json.loads(bad_args.stdout)["code"], "invalid_arguments")
        self.assertEqual(bad_args.stderr, "")


if __name__ == "__main__":
    unittest.main()
