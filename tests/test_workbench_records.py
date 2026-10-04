from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "study-material-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import export_content_records as export
from workflow_common import WorkflowError, canonical


def source_manifest(*, sha256="a" * 64, width=100, height=80, batch_id="batch-synthetic"):
    return {"schema_version": "swf.sources.v1", "batch_id": batch_id, "sources": [
        {"source_id": "original", "sha256": sha256, "width": width, "height": height, "token": "photo-01"},
    ]}


def draft(*, text="合成题干", refs=None, nodes=None, answer=None, missing=None):
    if refs is None:
        refs = [{"source_id": "original", "bbox": [2, 3, 90, 70]}]
    proposal = {"printed_text": text, "missing_fields": missing or [], "nodes": nodes or [], "answer": answer}
    return {"schema_version": "swb.material-draft.v1", "proposal": proposal,
            "sources": refs, "original_number": "练习 1"}


def content(*questions, diagrams=None, batch_id="batch-synthetic"):
    return {"schema_version": "swf.workbench-content.v1", "batch_id": batch_id,
            "questions": list(questions), "diagrams": list(diagrams or [])}


def question(identity="q1", material=None):
    return {"id": identity, "draft": material if material is not None else draft()}


def png_bytes(size=(16, 12), *, noise=False):
    if noise:
        raw = random.Random(17).randbytes(size[0] * size[1] * 3)
        image = Image.frombytes("RGB", size, raw)
    else:
        image = Image.new("RGB", size, (25, 80, 140))
    output = io.BytesIO()
    image.save(output, "PNG", compress_level=0 if noise else 6)
    return output.getvalue()


def safe_svg(padding=b""):
    return b'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="12">' + padding + b'<path d="M1 1L19 11"/></svg>'


def diagram(identity="d1", *, question_id="q1", source=None, png_key="figures/q1.png", vector_key="figures/q1.svg", **changes):
    row = {"id": identity, "question": question_id, "placement": "question", "png_key": png_key,
           "vector_key": vector_key, "source": source or {"source_id": "original", "bbox": [2, 3, 90, 70]},
           "alt": "合成线段示意图", "conditions": ["对应合成题目中的已知线段"],
           "width_points": 180, "min_label_points": 10, "independent_safe": True,
           "basis": "根据来源区域逐点核对标签。"}
    row.update(changes)
    return row


class WorkbenchRecordExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.assets = self.base / "assets"
        self.assets.mkdir()
        self.png = png_bytes()
        self.vector = safe_svg()
        (self.assets / "figures").mkdir()
        (self.assets / "figures/q1.png").write_bytes(self.png)
        (self.assets / "figures/q1.svg").write_bytes(self.vector)
        self.sources = source_manifest()

    def tearDown(self):
        self.temp.cleanup()

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(WorkflowError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_multiple_questions_unknown_text_and_automatic_namespaced_links(self):
        first = question("q1", draft(nodes=[
            {"kind": "knowledge", "data": {"definition": "两个分数相等时表示同一数值", "conditions": "分母非零"}},
            {"kind": "method", "data": {"name": "约分", "steps": "同除公因数"}},
            {"kind": "question_type", "data": {"name": "分数等值", "structural_features": "比较分数"}},
        ], answer={"body": "1/2", "formulas": [["t", "1/2"]], "basis": "复核约分结果。"}))
        second = question("q2", draft(text=None, missing=["printed_text"]))

        result = export.produce(content(first, second), self.sources, self.assets)

        self.assertEqual(result["schema_version"], "swb.skill-records.v2")
        rows = {row["id"]: row for row in result["records"]}
        self.assertEqual(rows["q1.question"]["data"]["printed_text"], "合成题干")
        self.assertIsNone(rows["q2.question"]["data"]["printed_text"])
        self.assertEqual(rows["q2.question"]["data"]["sources"], [{"source_id": "original", "bbox": [2, 3, 90, 70]}])
        self.assertEqual(rows["q1.node-0"]["kind"], "knowledge")
        self.assertEqual(rows["q1.node-1"]["kind"], "method")
        self.assertEqual(rows["q1.node-2"]["kind"], "question_type")
        self.assertEqual(rows["q1.link-0"]["data"], {"question": "q1.question", "node": "q1.node-0", "role": "applies"})
        self.assertEqual(rows["q1.link-1"]["data"]["role"], "primary")
        self.assertEqual(rows["q1.link-2"]["data"]["role"], "belongs")
        self.assertEqual(rows["q1.answer"]["data"]["question"], "q1.question")

    def test_diagram_keeps_exact_source_and_uses_actual_asset_sha_and_base64(self):
        result = export.produce(content(question(), diagrams=[diagram()]), self.sources, self.assets)

        rows = {row["id"]: row for row in result["records"]}
        record = rows["d1"]
        self.assertEqual(record["kind"], "diagram")
        self.assertEqual(record["data"]["question"], "q1.question")
        self.assertEqual(record["data"]["png_asset"], "figures/q1.png")
        self.assertEqual(record["data"]["vector_asset"], "figures/q1.svg")
        self.assertEqual(record["data"]["source"], rows["q1.question"]["data"]["sources"][0])
        self.assertEqual(result["assets"]["figures/q1.png"]["sha256"], hashlib.sha256(self.png).hexdigest())
        self.assertEqual(result["assets"]["figures/q1.svg"]["sha256"], hashlib.sha256(self.vector).hexdigest())
        self.assertEqual(result["assets"]["figures/q1.png"]["media_type"], "image/png")
        self.assertEqual(result["assets"]["figures/q1.svg"]["media_type"], "image/svg+xml")
        self.assertEqual(len(result["assets"]), 2)

    def test_duplicate_asset_key_is_idempotent_but_changed_bytes_conflict(self):
        other_question = question("q2")
        diagrams = [diagram("d1"), diagram("d2", question_id="q2", placement="answer")]
        result = export.produce(content(question(), other_question, diagrams=diagrams), self.sources, self.assets)
        self.assertEqual(len(result["assets"]), 2)

        changed_png = png_bytes(size=(16, 12), noise=True)
        with patch.object(export, "_read_asset", side_effect=[self.png, self.vector, changed_png, self.vector]):
            self.assert_code("asset_key_conflict", export.produce,
                             content(question(), other_question, diagrams=diagrams), self.sources, self.assets)

    def test_source_manifest_sha_dimensions_and_bbox_are_checked_without_guessing(self):
        bad_hash = source_manifest(sha256="A" * 64)
        self.assert_code("invalid_sources", export.produce, content(question()), bad_hash, self.assets)
        bad_width = source_manifest(width=True)
        self.assert_code("invalid_sources", export.produce, content(question()), bad_width, self.assets)
        outside = draft(refs=[{"source_id": "original", "bbox": [2, 3, 101, 70]}])
        self.assert_code("invalid_source_region", export.produce, content(question(material=outside)), self.sources, self.assets)
        fractional = draft(refs=[{"source_id": "original", "bbox": [2, 3, 10.5, 70]}])
        self.assert_code("invalid_source_region", export.produce, content(question(material=fractional)), self.sources, self.assets)

    def test_closed_fields_duplicate_ids_and_namespace_collisions_are_rejected(self):
        extra_content = content(question()) | {"unexpected": True}
        self.assert_code("invalid_content", export.produce, extra_content, self.sources, self.assets)
        extra_draft = draft() | {"unexpected": True}
        self.assert_code("invalid_draft", export.produce, content(question(material=extra_draft)), self.sources, self.assets)
        self.assert_code("duplicate_identity", export.produce, content(question(), question()), self.sources, self.assets)
        self.assert_code("duplicate_identity", export.produce,
                         content(question(), diagrams=[diagram("q1.question")]), self.sources, self.assets)

    def test_node_and_distinct_asset_count_limits_are_enforced(self):
        too_many_nodes = draft(nodes=[{"kind": "method", "data": {"name": f"方法 {i}"}} for i in range(4)])
        self.assert_code("invalid_draft", export.produce, content(question(material=too_many_nodes)), self.sources, self.assets)

        questions = [question(f"q{i}") for i in range(17)]
        diagrams = []
        figures = self.assets / "many"
        figures.mkdir()
        for index in range(17):
            png_key, vector_key = f"many/{index}.png", f"many/{index}.svg"
            (self.assets / png_key).write_bytes(self.png)
            (self.assets / vector_key).write_bytes(self.vector)
            diagrams.append(diagram(f"d{index}", question_id=f"q{index}",
                                    png_key=png_key, vector_key=vector_key))
        self.assert_code("asset_limit", export.produce,
                         content(*questions, diagrams=diagrams), self.sources, self.assets)

    def test_wrong_diagram_fields_source_mismatch_nonfinite_and_independent_safety_fail(self):
        extra = diagram() | {"unexpected": "drop me"}
        self.assert_code("invalid_diagram", export.produce, content(question(), diagrams=[extra]), self.sources, self.assets)
        mismatch = diagram(source={"source_id": "original", "bbox": [3, 3, 90, 70]})
        self.assert_code("diagram_source_mismatch", export.produce, content(question(), diagrams=[mismatch]), self.sources, self.assets)
        nonfinite = diagram(width_points=float("inf"))
        self.assert_code("invalid_diagram", export.produce, content(question(), diagrams=[nonfinite]), self.sources, self.assets)
        unsafe = diagram(independent_safe=1)
        self.assert_code("invalid_diagram", export.produce, content(question(), diagrams=[unsafe]), self.sources, self.assets)
        unsafe = diagram(independent_safe=False)
        self.assert_code("independent_hint", export.produce, content(question(), diagrams=[unsafe]), self.sources, self.assets)

    def test_diagram_alt_matches_native_two_thousand_character_limit(self):
        accepted = diagram(alt="a" * 2_000)
        result = export.produce(content(question(), diagrams=[accepted]), self.sources, self.assets)
        self.assertEqual(len(result["records"][-1]["data"]["alt"]), 2_000)
        rejected = diagram(alt="a" * 2_001)
        self.assert_code("invalid_content", export.produce, content(question(), diagrams=[rejected]), self.sources, self.assets)

    def test_unsafe_asset_paths_vectors_bad_hash_shape_and_byte_limit_fail_closed(self):
        for key in ("../secret.png", "https://example.invalid/x.png", "/tmp/x.png"):
            bad = diagram(png_key=key)
            self.assert_code("invalid_asset_key", export.produce, content(question(), diagrams=[bad]), self.sources, self.assets)
        link = self.assets / "figures/linked.png"
        link.symlink_to(self.assets / "figures/q1.png")
        bad_link = diagram(png_key="figures/linked.png")
        self.assert_code("symlink_path", export.produce, content(question(), diagrams=[bad_link]), self.sources, self.assets)
        for unsafe_vector in (b"<!DOCTYPE svg><svg/>", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
                              b'<svg xmlns="http://www.w3.org/2000/svg"><path onclick="go()"/></svg>',
                              b"not-a-vector"):
            vector_path = self.assets / "figures/bad.svg"
            vector_path.write_bytes(unsafe_vector)
            bad_vector = diagram(vector_key="figures/bad.svg")
            self.assert_code("unsafe_vector", export.produce, content(question(), diagrams=[bad_vector]), self.sources, self.assets)
        over_limit = self.assets / "figures/large.svg"
        over_limit.write_bytes(safe_svg(b" " * (export.MAX_ASSET_BYTES + 1)))
        bad_size = diagram(vector_key="figures/large.svg")
        self.assert_code("asset_size", export.produce, content(question(), diagrams=[bad_size]), self.sources, self.assets)

    def test_complete_canonical_package_has_one_megabyte_bound(self):
        noisy_png = png_bytes((350, 350), noise=True)
        huge_svg = safe_svg(b" " * (420 * 1024))
        self.assertLessEqual(len(noisy_png), export.MAX_ASSET_BYTES)
        self.assertLessEqual(len(huge_svg), export.MAX_ASSET_BYTES)
        (self.assets / "figures/large.png").write_bytes(noisy_png)
        (self.assets / "figures/large.svg").write_bytes(huge_svg)
        big_diagram = diagram(png_key="figures/large.png", vector_key="figures/large.svg")
        self.assert_code("output_too_large", export.produce, content(question(), diagrams=[big_diagram]), self.sources, self.assets)

    def test_cli_reads_strict_json_and_writes_private_exclusive_metadata_only(self):
        private = self.base / "private"
        private.mkdir(mode=0o700)
        private.chmod(0o700)
        content_path = self.base / "content.json"
        sources_path = self.base / "sources.json"
        content_value = content(question("q-secret", draft(text="secret-content")))
        content_path.write_bytes(canonical(content_value))
        sources_path.write_bytes(canonical(self.sources))
        output = private / "records.json"
        command = [sys.executable, str(SCRIPTS / "export_content_records.py"),
                   "--content", str(content_path), "--sources", str(sources_path),
                   "--asset-root", str(self.assets), "--output", str(output)]
        env = {key: value for key, value in os.environ.items() if not key.startswith("SWB_")}
        env["DJANGO_SETTINGS_MODULE"] = "missing_settings_module.must_not_be_imported"
        first = subprocess.run(command, cwd=SCRIPTS.parents[2], text=True, capture_output=True, env=env, check=False)
        self.assertEqual(first.returncode, 0, first.stderr)
        metadata = json.loads(first.stdout)
        self.assertEqual(set(metadata), {"sha256", "record_count", "asset_count", "database_opened", "review_state"})
        self.assertFalse(metadata["database_opened"])
        self.assertEqual(metadata["review_state"], "draft")
        self.assertNotIn("secret-content", first.stdout)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        original = output.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), metadata["sha256"])

        repeated = subprocess.run(command, cwd=SCRIPTS.parents[2], text=True, capture_output=True, env=env, check=False)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(output.read_bytes(), original)

        duplicated = self.base / "duplicate.json"
        duplicated.write_text('{"schema_version":"swf.workbench-content.v1","schema_version":"bad"}', encoding="utf-8")
        bad_command = [sys.executable, str(SCRIPTS / "export_content_records.py"),
                       "--content", str(duplicated), "--sources", str(sources_path),
                       "--asset-root", str(self.assets), "--output", str(private / "never.json")]
        rejected = subprocess.run(bad_command, cwd=SCRIPTS.parents[2], text=True, capture_output=True, env=env, check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse((private / "never.json").exists())

        nonfinite = self.base / "nonfinite.json"
        nonfinite.write_text('{"printed_text":NaN}', encoding="utf-8")
        bad_command[bad_command.index("--content") + 1] = str(nonfinite)
        rejected = subprocess.run(bad_command, cwd=SCRIPTS.parents[2], text=True, capture_output=True, env=env, check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertFalse((private / "never.json").exists())


if __name__ == "__main__":
    unittest.main()
