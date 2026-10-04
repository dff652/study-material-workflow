"""Counterexamples for companion scope, provenance and review claims."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/study-material-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))
from workflow_common import WorkflowError, canonical, digest
from solution_companion.make_demo import prepare_demo_inputs
from solution_companion.model import (
    asset_records, compile_documents, content_digest, leaf_parts, validate_content, validate_review,
)


def untested_review(content, recipe):
    scope = {"status": "not_tested", "reviewer": None, "notes": "等待实际审核。",
             "question_ids": [], "part_ids": []}
    platform = {"status": "not_tested", "word_version": None, "os_version": None,
                "document_ids": [], "evidence_sha256": {}}
    return {"schema_version": "swf.solution-review.v1", "content_sha256": content_digest(content),
            "recipe_sha256": recipe, "content": copy.deepcopy(scope), "math": copy.deepcopy(scope),
            "pdf_visual": {"status": "not_tested", "reviewer": None, "notes": "等待逐页检查。", "pages": []},
            "word_client": {"status": "not_tested", "reviewer": None, "notes": "两端待验。",
                            "platforms": {"PC": copy.deepcopy(platform), "macOS": copy.deepcopy(platform)}},
            "independent_reviews": []}


class SolutionModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.data = prepare_demo_inputs(Path(cls.temp.name) / "inputs")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def content(self):
        return copy.deepcopy(self.data["content"])

    def rejects(self, change, code=None):
        content = self.content(); change(content)
        with self.assertRaises(WorkflowError) as error:
            validate_content(content, self.data["sources"])
        if code:
            self.assertEqual(error.exception.code, code)

    def test_mixed_formats_cross_page_and_leaf_counts(self):
        content = self.content(); validate_content(content, self.data["sources"])
        self.assertEqual(sum(len(leaf_parts(q)) for q in content["questions"]), 4)
        plans = compile_documents(content)
        self.assertEqual(len(plans), 6)
        self.assertEqual(sum(len(p["formats"]) for p in plans), 10)
        combined = plans[-1]
        self.assertEqual(combined["document"].pages[0][-1].content[0][1][0], "A/1")
        self.assertEqual(combined["document"].pages[0][-1].content[0][3][0], "B/1")
        self.assertEqual(combined["page_questions"], [None, "power", "fractions", "fractions", "area"])
        self.assertEqual(combined["document"].pages[2:],
                         plans[1]["document"].pages + plans[2]["document"].pages)

    def test_parent_cycle_orphan_and_duplicate_leaf(self):
        self.rejects(lambda c: c["questions"][1]["parts"][0].update(parent_id="fraction-add"), "invalid_parent")
        self.rejects(lambda c: c["questions"][1]["parts"][1].update(parent_id="missing"), "invalid_parent")
        self.rejects(lambda c: c["questions"][1]["parts"][1].update(part_id="power-answer"), "duplicate_identity")
        self.rejects(lambda c: c["questions"][1]["parts"][0].update(answer="3/4"), "invalid_parent")

    def test_missing_transcription_answer_label_and_unit(self):
        self.rejects(lambda c: c["questions"][0]["statement"].update(text="计算3³。"), "missing_question_content")
        self.rejects(lambda c: c["questions"][0]["parts"][0].update(answer="9"), "missing_answer")
        self.rejects(lambda c: c["questions"][1]["parts"][2].update(label="(3)"), "missing_answer")
        self.rejects(lambda c: c["questions"][2]["parts"][0].update(unit="平方厘米"), "missing_answer")

    def test_unknown_is_retained_and_not_invented(self):
        self.rejects(lambda c: c["questions"][0]["statement"].update(status="partial"), "missing_unknown")
        self.rejects(lambda c: c["questions"][0]["parts"][0].update(answer=None), "missing_unknown")
        content = self.content(); content["questions"][0]["parts"][0]["answer"] = None
        content["questions"][0]["unknowns"].append("答案尚未核对")
        validate_content(content, self.data["sources"])
        self.assertEqual(content["questions"][2]["parts"][0]["unit"], None)

    def test_source_binding_order_and_regions(self):
        self.rejects(lambda c: c.update(sources_sha256="0" * 64), "stale_input")
        self.rejects(lambda c: c["questions"][1]["source_refs"][1].update(sequence=1), "invalid_sequence")
        self.rejects(lambda c: c["questions"][1]["source_refs"][1].update(region=[0, 0, 641, 160]), "invalid_region")
        self.rejects(lambda c: c["questions"][1]["source_refs"][0].update(source_id="unselected"), "missing_source")
        self.rejects(lambda c: c["assets"][0].update(region=[0, 0, 640, 160]), "invalid_region")

    def test_explicit_selected_counts_cannot_hide_missing_questions(self):
        content = self.content(); sources = copy.deepcopy(self.data["sources"])
        sources["expected_counts"] = {}
        content["sources_sha256"] = digest(canonical(sources))
        validate_content(content, sources)
        sources["expected_counts"]["parent_questions"] = 4
        content["sources_sha256"] = digest(canonical(sources))
        with self.assertRaises(WorkflowError) as error:
            validate_content(content, sources)
        self.assertEqual(error.exception.code, "coverage_mismatch")

    def test_original_pixel_identity_and_modified_resources(self):
        records = asset_records(self.data["content"], self.data["sources"], self.data["source_root"], self.data["asset_root"])
        self.assertEqual(set(records), {"original.png", "rectangle.png"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for item in self.data["asset_root"].iterdir():
                (root / item.name).write_bytes(item.read_bytes())
            from PIL import Image
            Image.new("RGB", (640, 160), "black").save(root / "original.png")
            changed = self.content(); sha = digest((root / "original.png").read_bytes())
            changed["assets"][0]["sha256"] = sha
            changed["questions"][0]["pages"][0][2]["content"]["sha256"] = sha
            with self.assertRaises(WorkflowError) as error:
                asset_records(changed, self.data["sources"], self.data["source_root"], root)
            self.assertEqual(error.exception.code, "stale_asset")

    def test_resource_escape_and_unused_declarations(self):
        self.rejects(lambda c: c["assets"][0].update(storage_key="../original.png"), "path_escape")
        self.rejects(lambda c: c["lectures"].append({"lecture_id": "unused", "title": "未选讲"}), "unused_input")
        self.rejects(lambda c: c["assets"][0].update(kind=[]), "invalid_companion")

    def test_partial_review_cannot_claim_full_pass_or_reuse_stale_recipe(self):
        content = self.content(); recipe = "a" * 64
        docs = [{"document_id": "combined", "page_count": 5}]
        review = untested_review(content, recipe)
        validate_review(review, content, recipe, docs)
        review["math"].update(status="pass", reviewer="reviewer", question_ids=["power"], part_ids=["power-answer"])
        with self.assertRaises(WorkflowError) as error:
            validate_review(review, content, recipe, docs)
        self.assertEqual(error.exception.code, "incomplete_review")
        review = untested_review(content, recipe); review["recipe_sha256"] = "b" * 64
        with self.assertRaises(WorkflowError) as error:
            validate_review(review, content, recipe, docs)
        self.assertEqual(error.exception.code, "stale_review")

    def test_word_pass_needs_every_platform_version_and_export(self):
        content = self.content(); recipe = "a" * 64
        docs = [{"document_id": "combined", "page_count": 5}]
        review = untested_review(content, recipe)
        for platform in review["word_client"]["platforms"].values():
            platform.update(status="pass", document_ids=["combined"])
        review["word_client"].update(status="pass", reviewer="user")
        with self.assertRaises(WorkflowError) as error:
            validate_review(review, content, recipe, docs)
        self.assertEqual(error.exception.code, "incomplete_review")

    def test_independent_review_cannot_mix_unrelated_question_and_leaf_scopes(self):
        content = self.content(); recipe = "a" * 64
        review = untested_review(content, recipe)
        review["independent_reviews"].append({"status": "pass", "reviewer": "independent",
            "notes": "反例范围", "question_ids": ["power"], "part_ids": ["area-answer"]})
        with self.assertRaises(WorkflowError) as error:
            validate_review(review, content, recipe, [{"document_id": "combined", "page_count": 5}])
        self.assertEqual(error.exception.code, "invalid_review")

    def test_independent_pass_needs_real_scope_without_forcing_answer_review(self):
        content = self.content(); recipe = "a" * 64
        docs = [{"document_id": "combined", "page_count": 5}]
        review = untested_review(content, recipe)
        item = {"status": "pass", "reviewer": "independent", "notes": "只检查题面来源。",
                "question_ids": [], "part_ids": []}
        review["independent_reviews"].append(item)
        with self.assertRaises(WorkflowError) as error:
            validate_review(review, content, recipe, docs)
        self.assertEqual(error.exception.code, "incomplete_review")
        item["question_ids"] = ["power"]
        validate_review(review, content, recipe, docs)
        for status in ["not_tested", "fail"]:
            item.update(status=status, question_ids=[])
            validate_review(review, content, recipe, docs)


if __name__ == "__main__":
    unittest.main()
