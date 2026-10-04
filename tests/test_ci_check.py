import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ci_check import CIError, _test_counts, prepare_output_root, strict_tests_accepted


class StrictTestAcceptanceTests(unittest.TestCase):
    def run_case(self, method):
        case_type = type("SyntheticTestCase", (unittest.TestCase,), {"test_generated": method})
        result = unittest.TestResult()
        case_type("test_generated").run(result)
        return result

    def test_zero_discovered_tests_fail(self):
        self.assertFalse(strict_tests_accepted(unittest.TestResult()))

    def test_skipped_tests_fail(self):
        def skip(self):
            self.skipTest("synthetic skip")

        self.assertFalse(strict_tests_accepted(self.run_case(skip)))

    def test_failures_and_errors_fail(self):
        def fail(self):
            self.fail("synthetic failure")

        def error(self):
            raise RuntimeError("synthetic error")

        self.assertFalse(strict_tests_accepted(self.run_case(fail)))
        self.assertFalse(strict_tests_accepted(self.run_case(error)))

    def test_nonempty_clean_result_passes(self):
        def pass_test(self):
            pass

        self.assertTrue(strict_tests_accepted(self.run_case(pass_test)))

    def test_expected_failure_is_rejected_and_not_counted_as_passed(self):
        @unittest.expectedFailure
        def expected_failure(self):
            self.fail("synthetic expected failure")

        result = self.run_case(expected_failure)
        self.assertEqual(len(result.expectedFailures), 1)
        self.assertFalse(strict_tests_accepted(result))
        self.assertEqual(
            _test_counts(result),
            {
                "discovered": 1,
                "passed": 0,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
                "expected_failures": 1,
                "unexpected_successes": 0,
            },
        )

    def test_unexpected_success_is_rejected_and_not_counted_as_passed(self):
        @unittest.expectedFailure
        def unexpected_success(self):
            pass

        result = self.run_case(unexpected_success)
        self.assertEqual(len(result.unexpectedSuccesses), 1)
        self.assertFalse(result.wasSuccessful())
        self.assertFalse(strict_tests_accepted(result))
        self.assertEqual(
            _test_counts(result),
            {
                "discovered": 1,
                "passed": 0,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
                "expected_failures": 0,
                "unexpected_successes": 1,
            },
        )


class OutputRootTests(unittest.TestCase):
    def test_nonempty_root_is_rejected_without_changing_its_contents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "evidence"
            root.mkdir()
            existing = root / "keep.txt"
            existing.write_text("preserve", encoding="utf-8")
            with self.assertRaises(CIError):
                prepare_output_root(root)
            self.assertEqual(existing.read_text(encoding="utf-8"), "preserve")

    def test_new_and_empty_roots_are_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            new = Path(temporary) / "new" / "evidence"
            self.assertEqual(prepare_output_root(new), new)
            empty = Path(temporary) / "empty"
            empty.mkdir()
            self.assertEqual(prepare_output_root(empty), empty)


if __name__ == "__main__":
    unittest.main()
