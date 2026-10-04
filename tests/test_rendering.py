import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/study-material-workflow/scripts"
ASSETS = SCRIPTS.parent / "assets"
sys.path.insert(0, str(SCRIPTS))

import check_environment
import render_packet
import verify_packet
from packet import packet_digest
from workflow_common import WorkflowError, canonical, digest, read_json


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.asset_root = self.root / "input-assets"
        self.asset_root.mkdir()
        self.font_config = read_json(ASSETS / "font-config.example.json")
        for key in ("regular_source", "bold_source", "math_source"):
            if not Path(self.font_config[key]).is_file():
                self.skipTest("Example system font files are not installed")
        self.packet = self._packet()

    def tearDown(self):
        self.temp.cleanup()

    def _diagram(self, color="#175A8E"):
        image = Image.new("RGB", (180, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.polygon([(20, 80), (90, 15), (160, 80)], outline=color, fill="#EAF3FA")
        draw.text((78, 78), "A", fill="black")
        path = self.asset_root / "triangle.png"
        image.save(path, format="PNG")
        return path.read_bytes()

    def _packet(self):
        packet = copy.deepcopy(read_json(ASSETS / "example-packet.json"))
        packet["batch_id"] = "synthetic-render-test"
        packet["sources_sha256"] = "1" * 64
        packet["catalog_sha256"] = "2" * 64
        for document in packet["documents"]:
            document["source"].update(source_id="synthetic-render-test", sha256=packet["catalog_sha256"])

        classification = packet["documents"][1]
        classification["pages"][0].append({
            "kind": "map",
            "content": {
                "root": ["分数运算"],
                "groups": [
                    {"label": ["通分"], "detail": ["分母相同"]},
                    {"label": ["约分"], "detail": ["结果最简"]},
                ],
            },
            "role": "classification",
        })

        evidence = packet["documents"][2]
        evidence["source"]["state"] = "legacy_unreviewed"
        practice = packet["documents"][3]
        practice["pages"].append([
            {"kind": "p", "content": "第二页：写出检查步驟。", "role": "question"},
            {"kind": "space", "content": 70, "role": "answer_space"},
        ])
        raw = self._diagram()
        practice["pages"][0].append({
            "kind": "diagram",
            "content": {
                "storage_key": "triangle.png",
                "sha256": digest(raw),
                "source_ref": "匿名坐标合成图",
                "alt": "用于独立练习的三角形示意",
                "width_mm": 55,
                "no_hint_confirmed": True,
            },
            "role": "question",
        })
        return packet

    def test_render_verify_reuse_asset_versioning_and_tamper_detection(self):
        output = self.root / "versions"
        first = render_packet.render_packet(self.packet, self.font_config, output, self.asset_root)
        self.assertFalse(first["reused"])
        self.assertEqual(first["documents"], 5)
        self.assertGreater(first["pdf_pages"], 5)
        report = verify_packet.verify_packet(first["directory"])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["documents"], 5)
        self.assertEqual(report["word_client"], "not_tested")
        self.assertEqual(report["human_review"], "not_tested")

        reused = render_packet.render_packet(self.packet, self.font_config, output, self.asset_root)
        self.assertTrue(reused["reused"])
        self.assertEqual(first["directory"], reused["directory"])

        manifest = read_json(Path(first["directory"]) / "render-manifest.json")
        packet_copy = read_json(Path(first["directory"]) / "packet.json")
        self.assertEqual(len(manifest["documents"]), 5)
        self.assertEqual(packet_copy["documents"][3]["source"]["state"], "draft")
        self.assertEqual(packet_copy["documents"][2]["source"]["state"], "legacy_unreviewed")
        self.assertEqual(manifest["documents"][3]["pages"], 2)

        changed = copy.deepcopy(self.packet)
        raw = self._diagram("#A32535")
        changed["documents"][3]["pages"][0][-1]["content"]["sha256"] = digest(raw)
        second = render_packet.render_packet(changed, self.font_config, output, self.asset_root)
        self.assertNotEqual(first["recipe_sha256"], second["recipe_sha256"])
        self.assertNotEqual(first["directory"], second["directory"])

        target = Path(second["directory"]) / "documents" / "example-01" / "document.pdf"
        target.write_bytes(target.read_bytes() + b"tampered")
        with self.assertRaises(WorkflowError) as caught:
            verify_packet.verify_packet(second["directory"])
        self.assertEqual(caught.exception.code, "render_integrity_error")

    def test_independent_hint_roles_and_diagrams_are_rejected(self):
        bad_role = copy.deepcopy(self.packet)
        bad_role["documents"][3]["pages"][0][1]["role"] = "method"
        with self.assertRaises(WorkflowError) as role_error:
            render_packet.render_packet(bad_role, self.font_config, self.root / "role-rejected", self.asset_root)
        self.assertEqual(role_error.exception.code, "independent_hint")

        bad_diagram = copy.deepcopy(self.packet)
        bad_diagram["documents"][3]["pages"][0][-1]["content"]["no_hint_confirmed"] = False
        with self.assertRaises(WorkflowError) as diagram_error:
            render_packet.render_packet(bad_diagram, self.font_config, self.root / "diagram-rejected", self.asset_root)
        self.assertEqual(diagram_error.exception.code, "independent_hint")

    def test_accepted_content_keeps_review_and_review_changes_new_version(self):
        accepted = copy.deepcopy(self.packet)
        accepted["documents"][0]["source"].update(state="accepted", revision_id="synthetic-revision-1")
        accepted["review"] = {
            "packet_sha256": packet_digest(accepted),
            "content": {"status": "pass", "reviewer": "synthetic-reviewer", "notes": "Fixture acceptance only."},
            "math": {"status": "pass", "reviewer": "synthetic-reviewer", "notes": "Fixture acceptance only."},
        }
        output = self.root / "accepted-versions"
        first = render_packet.render_packet(accepted, self.font_config, output, self.asset_root)
        manifest = read_json(Path(first["directory"]) / "render-manifest.json")
        stored_packet = read_json(Path(first["directory"]) / "packet.json")
        self.assertEqual(stored_packet["review"], accepted["review"])
        self.assertEqual(manifest["recipe"]["packet_record_sha256"], digest(canonical(accepted)))
        self.assertEqual(verify_packet.verify_packet(first["directory"])["status"], "passed")

        revised_review = copy.deepcopy(accepted)
        revised_review["review"]["content"]["notes"] = "A distinct synthetic note."
        second = render_packet.render_packet(revised_review, self.font_config, output, self.asset_root)
        self.assertEqual(first["packet_sha256"], second["packet_sha256"])
        self.assertNotEqual(first["recipe_sha256"], second["recipe_sha256"])
        self.assertNotEqual(first["directory"], second["directory"])

    def test_environment_reports_pdftoppm_availability(self):
        with tempfile.TemporaryDirectory() as font_root:
            with patch.object(check_environment.shutil, "which", return_value=None):
                missing = check_environment.check_environment(font_root)
            self.assertEqual(missing["renderer_tools"]["pdftoppm"], {"available": False, "path": None})
            self.assertIn("renderer_tool:pdftoppm", missing["missing"])
            with patch.object(check_environment.shutil, "which", return_value="/usr/bin/pdftoppm"):
                available = check_environment.check_environment(font_root)
            self.assertEqual(available["renderer_tools"]["pdftoppm"]["available"], True)
            self.assertNotIn("renderer_tool:pdftoppm", available["missing"])


if __name__ == "__main__":
    unittest.main()
