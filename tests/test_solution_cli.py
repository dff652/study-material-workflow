"""Exercise saved companion runs through the public CLI and real files."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/study-material-workflow/scripts"
sys.path.insert(0, str(SCRIPTS))
from solution_companion.make_demo import prepare_demo_inputs
from workflow_common import read_json, write_json


class SolutionCliTests(unittest.TestCase):
    def invoke(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPTS / "solution_companion/cli.py"), *map(str, args)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1)
        return result.returncode, json.loads(result.stdout)

    def test_saved_run_replay_input_change_failure_and_new_version(self):
        config = read_json(SCRIPTS.parent / "assets/font-config.example.json")
        if not all(Path(config[key]).is_file() for key in ("regular_source", "bold_source", "math_source")):
            self.skipTest("Explicit example fonts unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); data = prepare_demo_inputs(root / "inputs")
            write_json(root / "fonts.json", config)
            command = ["render", "--content", data["content_path"], "--sources", data["sources_path"],
                       "--source-root", data["source_root"], "--asset-root", data["asset_root"],
                       "--font-config", root / "fonts.json", "--output-root", root / "run"]
            code, first = self.invoke(*command)
            self.assertEqual(code, 0, first)
            pointer = Path(first["run"]); saved = pointer.read_bytes()
            code, resumed = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 0, resumed)
            self.assertEqual(resumed["word_client"], "not_tested")
            self.assertFalse(resumed["family_approved"])
            self.assertEqual(pointer.read_bytes(), saved)
            code, replay = self.invoke(*command)
            self.assertEqual(code, 0, replay); self.assertTrue(replay["reused"])
            self.assertEqual(pointer.read_bytes(), saved)
            old_version_files = {p.relative_to(first["directory"]).as_posix(): p.read_bytes()
                                 for p in Path(first["directory"]).rglob("*") if p.is_file()}

            bad = copy.deepcopy(data["content"])
            bad["questions"][0]["parts"][0]["answer"] = "9"
            write_json(data["content_path"], bad, replace=True)
            code, stale = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 2); self.assertEqual(stale["code"], "stale_run")
            code, failed = self.invoke(*command)
            self.assertEqual(code, 2); self.assertEqual(failed["code"], "missing_answer")
            self.assertEqual(pointer.read_bytes(), saved)
            failures = list((root / "run/failures").glob("*.json"))
            self.assertEqual(len(failures), 1)
            self.assertEqual(read_json(failures[0])["code"], "missing_answer")

            changed = copy.deepcopy(data["content"]); changed["revision_id"] = "v2"
            changed["questions"][0]["pages"][0].append(
                {"kind": "small", "content": "新版补充：检查相乘次数。", "role": "body"})
            write_json(data["content_path"], changed, replace=True)
            code, second = self.invoke(*command)
            self.assertEqual(code, 0, second)
            self.assertNotEqual(first["directory"], second["directory"])
            self.assertEqual(len(read_json(pointer)["versions"]), 2)
            self.assertEqual(old_version_files, {p.relative_to(first["directory"]).as_posix(): p.read_bytes()
                                               for p in Path(first["directory"]).rglob("*") if p.is_file()})

            font_bytes = (root / "fonts.json").read_bytes()
            (root / "fonts.json").write_bytes(font_bytes + b" ")
            code, stale_font = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 2); self.assertEqual(stale_font["code"], "stale_run")
            (root / "fonts.json").write_bytes(font_bytes)
            source = data["source_root"] / "page4.png"; original = source.read_bytes()
            source.write_bytes(original + b"changed")
            code, stale_original = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 2, stale_original)
            source.write_bytes(original)

            state = read_json(pointer); state["environment"]["python"] = "0.0.0"
            good_state = pointer.read_bytes(); write_json(pointer, state, replace=True)
            code, stale_environment = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 2); self.assertEqual(stale_environment["code"], "stale_run")
            pointer.write_bytes(good_state)
            code, recovered = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 0, recovered)
            state = read_json(pointer); state["versions"].append("/elsewhere/" + "a" * 24)
            write_json(pointer, state, replace=True)
            code, foreign = self.invoke("status", "--run", pointer)
            self.assertEqual(code, 2); self.assertEqual(foreign["code"], "invalid_run")

    def test_overlapping_sources_refuse_all_writes_and_unknown_command_is_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); data = prepare_demo_inputs(root / "inputs")
            before = {p.name: p.read_bytes() for p in data["source_root"].iterdir()}
            code, failure = self.invoke("render", "--content", data["content_path"],
                "--sources", data["sources_path"], "--source-root", data["source_root"],
                "--asset-root", data["asset_root"], "--font-config", SCRIPTS.parent / "assets/font-config.example.json",
                "--output-root", data["source_root"] / "bad-run")
            self.assertEqual(code, 2); self.assertEqual(failure["code"], "source_output_overlap")
            self.assertEqual(before, {p.name: p.read_bytes() for p in data["source_root"].iterdir()})
            code, error = self.invoke("unknown")
            self.assertEqual(code, 2); self.assertEqual(error["code"], "invalid_arguments")


if __name__ == "__main__":
    unittest.main()
