from pathlib import Path
import tempfile
import unittest

from skynet.fuzz import FastPolicyFuzzer


class FuzzV010Tests(unittest.TestCase):
    def test_governance_fuzzer_matches_all_expected_policy_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            report = FastPolicyFuzzer(Path(td), seed=42).run(cases=5000)
            self.assertEqual(report.cases, 5000)
            self.assertEqual(report.pass_rate, 1.0, report.failures)
            self.assertEqual(report.passed, 5000)
            self.assertEqual(report.permission_checks, 20_000)
            self.assertGreater(report.cases_per_second, 0)


if __name__ == "__main__":
    unittest.main()
