from __future__ import annotations

import json
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "study-material-workflow" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import adapt_catalog
import collect_sources
import workflow_common


def make_image(path: Path, color=(15, 30, 45)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (10, 8), color).save(path, format="PNG")


def legacy_row(book, num, group, photo, *, aux="", feature="synthetic feature"):
    return {
        "book": book,
        "num": num,
        "group": group,
        "photo": photo,
        "feature": feature,
        "method": "synthetic method note",
        "tag": "synthetic tag",
        "tip": "synthetic tip",
        "aux": aux,
    }


def profile(namespace="calculation", *, books=None, separator="/", allow_sides=False, aliases=None):
    return {
        "profile_id": f"{namespace}-synthetic-v1",
        "namespace": namespace,
        "classification_revision": f"{namespace}-six-methods-test-v1",
        "books": books or (["J1", "J2", "W1", "W2", "W3", "W4"] if namespace == "calculation"
                           else ["J3", "J4", "W5", "W6", "W7", "W8", "W9"]),
        "photo_separator": separator,
        "allow_sides": allow_sides,
        "groups": {str(number): f"synthetic method {number}" for number in range(1, 7)},
        "aux_aliases": aliases or {},
    }


class AdaptCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.source_root = self.base / "sources"
        self.source_root.mkdir()
        self.manifest = self.make_manifest({
            ("J1", "000001"), ("J1", "000002"), ("J1", "000003"),
            ("W5", "000101"), ("W5", "000102"), ("W5", "000103"), ("W5", "000104"),
            ("J3", "000201"),
        })

    def tearDown(self):
        self.temp.cleanup()

    def make_manifest(self, sources):
        selected = []
        for index, (book, token) in enumerate(sorted(sources)):
            key = f"{book}-{token}.png"
            make_image(self.source_root / key, color=(index + 1, 30, 45))
            selected.append({"path": key, "book": book, "token": token,
                             "page_order": index + 1 if index % 2 == 0 else None})
        return collect_sources.collect_sources(
            self.source_root, {"batch_id": "catalog-synthetic", "files": selected}
        )

    def error_code(self, code, function, *args, **kwargs):
        with self.assertRaises(workflow_common.WorkflowError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_calculation_preserves_raw_fields_and_resolves_ordered_cross_page_refs(self):
        source_row = legacy_row("J1", "12(3)-2", 1, "000001/000002", aux="5;6", feature="exact synthetic text")
        root_row = legacy_row("J1", "12", 2, "000003", aux="1")

        result = adapt_catalog.adapt_catalog([source_row, root_row], self.manifest,
                                             profile(aliases={"一半模型": 1}))

        self.assertEqual(result["counts"], {
            "sources": 8, "parent_questions": 1, "entries": 2, "question_nodes": 3,
        })
        child = result["entries"][0]
        self.assertEqual(child["raw"], source_row)
        self.assertEqual(child["display_number"], "12(3)-2")
        parent_node = next(node for node in result["nodes"] if node["display_number"] == "12(3)")
        self.assertEqual(child["parent_id"], parent_node["question_id"])
        self.assertEqual([ref["sequence"] for ref in child["photo_refs"]], [1, 2])
        self.assertEqual([ref["granularity"] for ref in child["photo_refs"]], ["whole_image", "whole_image"])
        self.assertTrue(all(ref["region"] is None for ref in child["photo_refs"]))
        self.assertEqual(child["auxiliary_method_ids"], [
            adapt_catalog._method_id("calculation", 5), adapt_catalog._method_id("calculation", 6),
        ])
        self.assertEqual(child["review_state"], "draft")
        self.assertIn("printed_text_missing", child["gaps"])
        self.assertEqual(parent_node["node_type"], "parent")
        self.assertEqual(result, adapt_catalog.adapt_catalog([source_row, root_row], self.manifest,
                                                              profile(aliases={"一半模型": 1})))

    def test_geometry_sides_aliases_unknowns_and_namespace_separation(self):
        geometry = profile("geometry", separator="+", allow_sides=True,
                           aliases={"鸟头": 4, "等高比例": 2})
        rows = [
            legacy_row("W5", "4(左)", 2, "000101", aux="鸟头"),
            legacy_row("W5", "4(右)", 3, "000102", aux="泛称面积加减"),
            legacy_row("W5", "4(1)-2", 1, "000103+000104", aux="4"),
        ]

        result = adapt_catalog.adapt_catalog(rows, self.manifest, geometry)

        self.assertEqual(result["counts"]["parent_questions"], 1)
        self.assertEqual(result["counts"]["entries"], 3)
        self.assertEqual(result["counts"]["question_nodes"], 5)
        root_id = adapt_catalog._question_id("catalog-synthetic", "geometry", "W5", "4")
        left, right, child = result["entries"]
        self.assertEqual(left["parent_id"], root_id)
        self.assertEqual(right["parent_id"], root_id)
        self.assertEqual(child["parent_id"], adapt_catalog._question_id("catalog-synthetic", "geometry", "W5", "4(1)"))
        self.assertEqual(len(child["photo_refs"]), 2)
        self.assertEqual([ref["sequence"] for ref in child["photo_refs"]], [1, 2])
        self.assertEqual(left["auxiliary_method_ids"], [adapt_catalog._method_id("geometry", 4)])
        self.assertEqual(right["auxiliary_method_ids"], [])
        warning = next(item for item in result["warnings"] if item["question_id"] == right["question_id"])
        self.assertEqual(warning["code"], "unknown_auxiliary_method")
        self.assertEqual(warning["raw_value"], "泛称面积加减")
        self.assertIn("unknown_auxiliary_method", right["gaps"])

        calc_row = legacy_row("J1", "1", 4, "000001")
        calc_result = adapt_catalog.adapt_catalog([calc_row], self.manifest, profile())
        self.assertNotEqual(calc_result["entries"][0]["primary_method_id"], child["primary_method_id"])

    def test_known_alias_must_agree_with_numeric_prefix_and_unknown_text_stays_unmapped(self):
        geometry = profile("geometry", separator="+", allow_sides=True, aliases={"鸟头": 4})
        row = legacy_row("W5", "1", 1, "000101", aux="2 鸟头")
        self.error_code("auxiliary_mapping_conflict", adapt_catalog.adapt_catalog, [row], self.manifest, geometry)

        unknown = legacy_row("W5", "1", 1, "000101", aux="相似")
        result = adapt_catalog.adapt_catalog([unknown], self.manifest, geometry)
        self.assertEqual(result["entries"][0]["auxiliary_method_ids"], [])
        self.assertEqual(result["warnings"][0]["raw_value"], "相似")
        self.assertEqual(result["entries"][0]["raw"]["aux"], "相似")

    def test_invalid_numbers_groups_books_rows_duplicates_and_missing_sources_fail(self):
        calc = profile()
        row = legacy_row("J1", "1", 1, "000001")
        self.error_code("invalid_question_number", adapt_catalog.adapt_catalog,
                        [legacy_row("J1", "1(左)", 1, "000001")], self.manifest, calc)
        self.error_code("unknown_auxiliary_group", adapt_catalog.adapt_catalog,
                        [legacy_row("J1", "1", 1, "000001", aux="7")], self.manifest, calc)
        self.error_code("unknown_group", adapt_catalog.adapt_catalog,
                        [legacy_row("J1", "1", 7, "000001")], self.manifest, calc)
        self.error_code("unknown_book", adapt_catalog.adapt_catalog,
                        [legacy_row("W5", "1", 1, "000101")], self.manifest, calc)
        self.error_code("duplicate_question_number", adapt_catalog.adapt_catalog,
                        [row, dict(row)], self.manifest, calc)
        self.error_code("invalid_catalog_row", adapt_catalog.adapt_catalog,
                        [{key: value for key, value in row.items() if key != "tip"}], self.manifest, calc)
        self.error_code("missing_source", adapt_catalog.adapt_catalog,
                        [legacy_row("J1", "1", 1, "000999")], self.manifest, calc)
        self.error_code("missing_source", adapt_catalog.adapt_catalog,
                        [legacy_row("W5", "1", 1, "000201")], self.manifest,
                        profile("geometry", separator="+", allow_sides=True))

    def test_catalog_output_same_content_is_idempotent_and_different_content_conflicts(self):
        row = legacy_row("J1", "1", 1, "000001")
        adapted = adapt_catalog.adapt_catalog([row], self.manifest, profile())
        output = self.base / "catalog.json"
        self.assertTrue(workflow_common.write_json(output, adapted))
        self.assertFalse(workflow_common.write_json(output, adapted))
        changed = dict(adapted)
        changed["profile_id"] = "changed-profile"
        self.error_code("output_conflict", workflow_common.write_json, output, changed)

    def test_declared_parent_and_entry_counts_must_match_catalog(self):
        rows = [legacy_row("J1", "2(1)-1", 1, "000001"), legacy_row("J1", "2", 1, "000002")]
        manifest = copy.deepcopy(self.manifest)
        manifest["expected_counts"] = {"parent_questions": 1, "entries": 2}
        result = adapt_catalog.adapt_catalog(rows, manifest, profile())
        self.assertEqual(result["counts"]["parent_questions"], manifest["expected_counts"]["parent_questions"])
        self.assertEqual(result["counts"]["entries"], manifest["expected_counts"]["entries"])

        for field, wrong_count in (("parent_questions", 2), ("entries", 3)):
            with self.subTest(field=field):
                mismatched = copy.deepcopy(manifest)
                mismatched["expected_counts"][field] = wrong_count
                self.error_code("catalog_count_mismatch", adapt_catalog.adapt_catalog, rows, mismatched, profile())

    def test_cli_reads_old_json_array_and_writes_catalog_json(self):
        row = legacy_row("J1", "1", 1, "000001")
        manifest_path = self.base / "manifest.json"
        profile_path = self.base / "profile.json"
        rows_path = self.base / "legacy.json"
        output_path = self.base / "catalog.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        profile_path.write_text(json.dumps(profile()), encoding="utf-8")
        rows_path.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "adapt_catalog.py"), "--manifest", str(manifest_path),
             "--profile", str(profile_path), "--catalog", str(rows_path), "--output", str(output_path)],
            cwd=SCRIPTS.parents[2], text=True, capture_output=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["counts"]["entries"], 1)
        self.assertEqual(workflow_common.read_json(output_path)["schema_version"], "swf.catalog.v1")


if __name__ == "__main__":
    unittest.main()
