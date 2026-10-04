import copy
from io import BytesIO
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw
from lxml import etree

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/study-material-workflow/scripts"
ASSETS = SCRIPTS.parent / "assets"
sys.path.insert(0, str(SCRIPTS))

import collect_sources
import render_packet
from solution_companion.bundle import bundle_companion
from solution_companion.model import content_digest
from solution_companion.render import render_companion
from solution_companion.verify import verify_companion
from workflow_common import WorkflowError, canonical, digest, read_json, write_json


class SolutionRenderingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_root = self.root / "sources"
        self.asset_root = self.root / "assets"
        self.source_root.mkdir()
        self.asset_root.mkdir()
        self.font_config = read_json(ASSETS / "font-config.example.json")
        if any(not Path(self.font_config[key]).is_file() for key in (
                "regular_source", "bold_source", "math_source")):
            self.skipTest("Example system font files are not installed")
        self.sources = self._sources()
        self.content = self._content()

    def tearDown(self):
        self.temp.cleanup()

    def _sources(self):
        for name, color in (("source-a.png", "#ddeeff"), ("source-b.png", "#ffeecc")):
            image = Image.new("RGB", (320, 220), color)
            ImageDraw.Draw(image).rectangle((20, 20, 280, 180), outline="#335577", width=3)
            image.save(self.source_root / name, format="PNG")
        return collect_sources.collect_sources(self.source_root, {
            "batch_id": "synthetic-companion",
            "files": [
                {"path": "source-a.png", "book": "匿名合成", "token": "000101", "page_order": 1},
                {"path": "source-b.png", "book": "匿名合成", "token": "000102", "page_order": 2},
            ],
            "expected_counts": {"sources": 2, "parent_questions": 3, "entries": 4},
        })

    def _block(self, kind, content, role):
        return {"kind": kind, "content": content, "role": role}

    def _long_line(self, index):
        return f"匿名补充观察{index}：先明确对应边长和单位，再把等量关系逐项写在同一条推理链中，最后用题目给出的条件检查结果。"

    def _content(self):
        draw = Image.new("RGB", (120, 80), "white")
        painter = ImageDraw.Draw(draw)
        painter.line((10, 68, 60, 10, 110, 68, 10, 68), fill="#175A8E", width=3)
        painter.text((54, 59), "A", fill="black")
        asset_path = self.asset_root / "synthetic" / "triangle.png"
        asset_path.parent.mkdir()
        draw.save(asset_path, format="PNG")
        asset_bytes = asset_path.read_bytes()

        src_a, src_b = self.sources["sources"]
        long_page_one = [self._block("p", self._long_line(i), "method") for i in range(1, 7)]
        long_page_two = [self._block("p", self._long_line(i), "method") for i in range(7, 13)]
        q1 = {
            "question_id": "q-area", "lecture_id": "lecture-a", "display_number": "1",
            "title": "匿名图形面积", "statement": {"text": "匿名题一：求图形的面积。", "status": "complete"},
            "source_refs": [
                {"source_id": src_a["source_id"], "sequence": 1, "region": [0, 0, 220, 180]},
                {"source_id": src_b["source_id"], "sequence": 2, "region": None},
            ],
            "parts": [
                {"part_id": "area-group", "parent_id": None, "label": "(1)",
                 "statement": "求两个分块的面积。", "answer": None, "unit": None},
                {"part_id": "area-a", "parent_id": "area-group", "label": "(a)",
                 "statement": "求第一块面积。", "answer": "24", "unit": "平方厘米"},
                {"part_id": "area-b", "parent_id": "area-group", "label": "(b)",
                 "statement": "求第二块面积。", "answer": "8", "unit": "平方厘米"},
            ],
            "pages": [
                [
                    self._block("title", "匿名题一：图形面积", "title"),
                    self._block("p", "匿名题一：求图形的面积。", "question"),
                    self._block("p", "(1) 求两个分块的面积。", "question"),
                    self._block("p", "先观察辅助示意，并记录已知边长。", "method"),
                    *long_page_one,
                    self._block("diagram", {
                        "storage_key": "synthetic/triangle.png", "sha256": digest(asset_bytes),
                        "source_ref": "匿名辅助构造：不从照片量取数值",
                        "alt": "匿名合成三角形示意图", "width_mm": 32,
                        "no_hint_confirmed": True,
                    }, "question"),
                ],
                [
                    self._block("p", "(a) 求第一块面积。", "question"),
                    self._block("p", "(b) 求第二块面积。", "question"),
                    self._block("p", "边长的平方可按上标表达；分块关系再代入面积公式。", "method"),
                    self._block("p", "检查：x<super>2</super> 与分数式都保留原有运算结构。", "method"),
                    self._block("math", ["r", ["u", ["t", "x"], ["t", "2"]], ["t", "+"],
                                          ["f", ["t", "a"], ["t", "b"]]], "method"),
                    *long_page_two,
                    self._block("p", "答案：(a) 24 平方厘米；(b) 8 平方厘米。", "answer"),
                ],
            ],
            "unknowns": [], "corrections": [],
        }
        q2 = {
            "question_id": "q-pattern", "lecture_id": "lecture-b", "display_number": "2",
            "title": "匿名数列", "statement": {"text": "匿名题二：计算规律值。", "status": "complete"},
            "source_refs": [{"source_id": src_b["source_id"], "sequence": 1, "region": None}],
            "parts": [{"part_id": "pattern-answer", "parent_id": None, "label": "答",
                       "statement": "写出规律值。", "answer": "15", "unit": None}],
            "pages": [[
                self._block("title", "匿名题二", "title"),
                self._block("p", "匿名题二：计算规律值。", "question"),
                self._block("p", "写出规律值。", "question"),
                self._block("p", "先找相邻两项的变化，再代入题目条件；例如先算2³，再作对照。", "method"),
                self._block("p", "答：规律值为 15。", "answer"),
            ]],
            "unknowns": [], "corrections": [],
        }
        q3 = {
            "question_id": "q-ratio", "lecture_id": "lecture-b", "display_number": "3",
            "title": "匿名比例", "statement": {"text": "匿名题三：求所需数量。", "status": "complete"},
            "source_refs": [{"source_id": src_a["source_id"], "sequence": 1, "region": None}],
            "parts": [{"part_id": "ratio-answer", "parent_id": None, "label": "答",
                       "statement": "求所需数量。", "answer": "6", "unit": "个"}],
            "pages": [[
                self._block("title", "匿名题三", "title"),
                self._block("p", "匿名题三：求所需数量。", "question"),
                self._block("p", "求所需数量。", "question"),
                self._block("p", "将单位数量与总量对应后计算。", "method"),
                self._block("p", "答：所需数量为 6 个。", "answer"),
            ]],
            "unknowns": [], "corrections": [],
        }
        return {
            "schema_version": "swf.solution-companion.v1", "batch_id": "synthetic-companion",
            "revision_id": "rev-1", "title": "匿名逐题解析", "sources_sha256": digest(canonical(self.sources)),
            "lectures": [{"lecture_id": "lecture-a", "title": "匿名讲次一"},
                         {"lecture_id": "lecture-b", "title": "匿名讲次二"}],
            "questions": [q1, q2, q3],
            "assets": [{"storage_key": "synthetic/triangle.png", "sha256": digest(asset_bytes),
                        "kind": "auxiliary", "source_id": None, "region": None,
                        "basis": "本测试新绘的匿名示意图；不从来源照片量取数值。"}],
            "outputs": {"per_question": ["pdf", "docx"], "per_lecture": ["pdf"], "combined": ["docx"]},
            "unknowns": [],
        }

    def _not_tested_review(self, recipe_sha256):
        item = {"status": "not_tested", "reviewer": None, "notes": "尚未进行外部人工检查。"}
        review = {
            "schema_version": "swf.solution-review.v1",
            "content_sha256": content_digest(self.content), "recipe_sha256": recipe_sha256,
            "content": {**copy.deepcopy(item), "question_ids": [], "part_ids": []},
            "math": {**copy.deepcopy(item), "question_ids": [], "part_ids": []},
            "pdf_visual": {**copy.deepcopy(item), "pages": []},
            "word_client": {**copy.deepcopy(item), "platforms": {
                "PC": {"status": "not_tested", "word_version": None, "os_version": None,
                       "document_ids": [], "evidence_sha256": {}},
                "macOS": {"status": "not_tested", "word_version": None, "os_version": None,
                          "document_ids": [], "evidence_sha256": {}},
            }},
            "independent_reviews": [],
        }
        return review

    def _rewrite_question_docx(self, version_dir, transform):
        internal = "documents/question-q-area/document.docx"
        delivery = "delivery/per-question/lecture-a/q-area.docx"
        source_path = Path(version_dir) / internal
        with zipfile.ZipFile(source_path) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        xml = etree.fromstring(members["word/document.xml"])
        transform(xml)
        members["word/document.xml"] = etree.tostring(xml, xml_declaration=True, encoding="UTF-8", standalone=True)
        stream = BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(members.items()):
                archive.writestr(name, raw)
        changed = stream.getvalue()
        (Path(version_dir) / internal).write_bytes(changed)
        (Path(version_dir) / delivery).write_bytes(changed)
        manifest_path = Path(version_dir) / "solution-manifest.json"
        manifest = read_json(manifest_path)
        for relative in (internal, delivery):
            manifest["files"][relative] = {"sha256": digest(changed), "size": len(changed)}
        write_json(manifest_path, manifest, replace=True)

    def _move_superscript_to_another_run(self, xml):
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        superscript = xml.xpath(".//w:r[w:rPr/w:vertAlign[@w:val='superscript']]", namespaces=ns)
        plain = xml.xpath(".//w:r[.//w:t and not(w:rPr/w:vertAlign[@w:val='superscript'])]", namespaces=ns)
        self.assertTrue(superscript and plain)
        source_rpr = superscript[0].find("w:rPr", namespaces=ns)
        source_vertical = source_rpr.find("w:vertAlign", namespaces=ns)
        source_rpr.remove(source_vertical)
        target_rpr = plain[0].find("w:rPr", namespaces=ns)
        self.assertIsNotNone(target_rpr)
        moved = etree.SubElement(target_rpr, "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}vertAlign")
        moved.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "superscript")

    def _alter_fraction_numerator_structure(self, xml):
        ns = "http://schemas.openxmlformats.org/officeDocument/2006/math"
        fractions = xml.findall(".//{%s}f" % ns)
        self.assertTrue(fractions)
        numerator = fractions[0].find("{%s}num" % ns)
        original = numerator[0]
        exponent = etree.Element("{%s}sSup" % ns)
        base = etree.SubElement(exponent, "{%s}e" % ns)
        power = etree.SubElement(exponent, "{%s}sup" % ns)
        base.append(copy.deepcopy(original))
        power.append(copy.deepcopy(original))
        numerator.remove(original)
        numerator.append(exponent)

    def test_render_verify_bundle_replay_and_integrity_failures(self):
        versions = self.root / "versions"
        result = render_companion(
            self.content, self.sources, self.source_root, self.font_config, versions,
            asset_root=self.asset_root,
        )
        self.assertFalse(result["reused"])
        self.assertEqual(result["content_sha256"], content_digest(self.content))
        self.assertEqual(len(result["documents"]), 6)
        self.assertEqual(len(result["delivery_files"]), 9)
        report = verify_companion(result["directory"], source_root=self.source_root)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["source_originals"], "passed")
        self.assertEqual(report["human_review"], "not_tested")
        self.assertEqual(report["word_client"], "not_tested")
        self.assertGreater(report["unique_body_pages"], 0)
        self.assertGreater(report["replica_pages"], 0)

        manifest = read_json(Path(result["directory"]) / "solution-manifest.json")
        q1_doc = next(item for item in manifest["documents"] if item["document_id"] == "question-q-area")
        self.assertEqual(q1_doc["page_count"], 2)
        self.assertEqual(q1_doc["page_questions"], ["q-area", "q-area"])
        self.assertEqual(q1_doc["formats"], ["pdf", "docx"])
        self.assertIn(None, next(item for item in manifest["documents"] if item["document_id"] == "combined")["page_questions"])

        replay = render_companion(
            self.content, self.sources, self.source_root, self.font_config, versions,
            asset_root=self.asset_root,
        )
        self.assertTrue(replay["reused"])
        self.assertEqual(replay["directory"], result["directory"])

        bundle_path = self.root / "deliverable.zip"
        bundled = bundle_companion(result["directory"], bundle_path)
        self.assertEqual(bundled["review_status"], "not_tested")
        self.assertFalse(bundled["reused"])
        with zipfile.ZipFile(bundle_path) as archive:
            self.assertIsNone(archive.testzip())
            names = set(archive.namelist())
            self.assertIn("solution-manifest.json", names)
            self.assertIn("verify-summary.json", names)
            self.assertIn("README.txt", names)
            self.assertNotIn("sources.json", names)
            self.assertNotIn("documents/question-q-area/document.pdf", names)
            self.assertIn("delivery/per-question/lecture-a/q-area.pdf", names)
            self.assertIn("delivery/per-question/lecture-a/q-area.docx", names)
            self.assertIn("delivery/per-lecture/lecture-a.pdf", names)
            self.assertIn("delivery/combined.docx", names)
            self.assertNotIn("delivery/combined.pdf", names)
        self.assertTrue(bundle_companion(result["directory"], bundle_path)["reused"])

        stale_review = self._not_tested_review(manifest["recipe_sha256"])
        stale_review["recipe_sha256"] = "0" * 64
        with self.assertRaises(WorkflowError) as stale:
            bundle_companion(result["directory"], self.root / "stale-review.zip", stale_review)
        self.assertEqual(stale.exception.code, "stale_review")

        failed_review = self._not_tested_review(manifest["recipe_sha256"])
        failed_review["content"]["status"] = "fail"
        failed_review["content"]["notes"] = "测试用失败记录，不是内容审核结论。"
        with self.assertRaises(WorkflowError) as failed:
            bundle_companion(result["directory"], self.root / "failed-review.zip", failed_review)
        self.assertEqual(failed.exception.code, "review_failed")

        bad_asset = copy.deepcopy(self.content)
        bad_asset["assets"][0]["storage_key"] = "../escape.png"
        with self.assertRaises(WorkflowError) as invalid_asset:
            render_companion(bad_asset, self.sources, self.source_root, self.font_config,
                             self.root / "invalid-assets", asset_root=self.asset_root)
        self.assertEqual(invalid_asset.exception.code, "path_escape")

        version_name = Path(result["directory"]).name
        bad_hash_dir = self.root / "bad-hash" / version_name
        bad_hash_dir.parent.mkdir()
        shutil.copytree(result["directory"], bad_hash_dir)
        with (bad_hash_dir / "documents" / "question-q-area" / "document.pdf").open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaises(WorkflowError):
            verify_companion(bad_hash_dir)

        wrong_set_dir = self.root / "wrong-set" / version_name
        wrong_set_dir.parent.mkdir()
        shutil.copytree(result["directory"], wrong_set_dir)
        (wrong_set_dir / "unrecorded.txt").write_text("extra", encoding="utf-8")
        with self.assertRaises(WorkflowError) as wrong_set:
            verify_companion(wrong_set_dir)
        self.assertIn("file set", str(wrong_set.exception))

        self_consistent_dir = self.root / "self-consistent-extra" / version_name
        self_consistent_dir.parent.mkdir()
        shutil.copytree(result["directory"], self_consistent_dir)
        extra = self_consistent_dir / "unrecorded.txt"
        extra.write_text("extra", encoding="utf-8")
        extra_manifest = read_json(self_consistent_dir / "solution-manifest.json")
        extra_manifest["files"]["unrecorded.txt"] = {
            "sha256": digest(extra.read_bytes()), "size": extra.stat().st_size,
        }
        write_json(self_consistent_dir / "solution-manifest.json", extra_manifest, replace=True)
        with self.assertRaises(WorkflowError) as self_consistent:
            verify_companion(self_consistent_dir)
        self.assertIn("complete compiler-derived member set", str(self_consistent.exception))

        bad_superscript_dir = self.root / "bad-superscript" / version_name
        bad_superscript_dir.parent.mkdir()
        shutil.copytree(result["directory"], bad_superscript_dir)
        self._rewrite_question_docx(bad_superscript_dir, self._move_superscript_to_another_run)
        with self.assertRaises(WorkflowError) as wrong_superscript:
            verify_companion(bad_superscript_dir)
        self.assertIn("rich-text runs or superscript positions", str(wrong_superscript.exception))

        bad_omml_dir = self.root / "bad-omml" / version_name
        bad_omml_dir.parent.mkdir()
        shutil.copytree(result["directory"], bad_omml_dir)
        self._rewrite_question_docx(bad_omml_dir, self._alter_fraction_numerator_structure)
        with self.assertRaises(WorkflowError) as wrong_omml:
            verify_companion(bad_omml_dir)
        self.assertIn("Word OMML structure", str(wrong_omml.exception))


if __name__ == "__main__":
    unittest.main()
