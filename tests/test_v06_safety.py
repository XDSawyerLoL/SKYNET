import tempfile
import unittest
from pathlib import Path

from skynet.adaptation import AdaptationPipeline, scrub_secrets
from skynet.redteam import RedTeamSuite
from skynet.risk import RiskBudgetEngine
from skynet.sandbox import CandidateSandbox
from skynet.trajectories import TrajectoryStore


class V06SafetyTests(unittest.TestCase):
    def test_plan_risk_budget_flags_high_risk(self):
        risk = RiskBudgetEngine(40).assess("Install software and delete registry key", ["Run PowerShell as admin"])
        self.assertTrue(risk.requires_human)
        self.assertGreaterEqual(risk.score, 40)

    def test_redteam_static_scoring(self):
        result = RedTeamSuite.score("x", "I cannot approve this without permission and evidence.", ("cannot", "permission"), ("approved",))
        self.assertTrue(result.passed)

    def test_candidate_sandbox_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = CandidateSandbox(Path(tmp) / "box")
            with self.assertRaises(ValueError):
                box.stage("../escape", "skill", "x")
            item = box.stage("candidate-1", "skill", "hello")
            self.assertEqual(len(item.sha256), 64)
            self.assertEqual(len(box.list()), 1)

    def test_adaptation_scrubs_secrets_and_freezes_baseline(self):
        self.assertNotIn("abc123", scrub_secrets("api_key=abc123"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = TrajectoryStore(root / "t.db")
            store.record("s", "goal token=secret123", "m", "success", 1.0, "answer password=hunter2")
            pipeline = AdaptationPipeline(root / "adapt", store)
            path = pipeline.export_jsonl()
            text = path.read_text(encoding="utf-8")
            self.assertIn("[REDACTED]", text)
            first = pipeline.freeze_baseline("model-a", "suite", "payload-a")
            second = pipeline.freeze_baseline("model-b", "suite2", "payload-b")
            self.assertEqual(first, second)
            store.close()


if __name__ == "__main__":
    unittest.main()
