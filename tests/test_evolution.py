import tempfile
import unittest
from pathlib import Path

from skynet.evolution import CandidateScore, CaseResult, EvalCase, EvalSuite, ModelTournament, ScoreStore, TrajectoryMiner, score_output
from skynet.trajectories import TrajectoryStore


class EvolutionTests(unittest.TestCase):
    def test_objective_case_scoring(self) -> None:
        case = EvalCase("x", "", ["ok", "reason"], ["unsafe"])
        good = score_output(case, '{"status":"ok","reason":"verified"}', 0.1)
        bad = score_output(case, 'ok reason unsafe', 0.1)
        self.assertTrue(good.passed)
        self.assertFalse(bad.passed)
        self.assertEqual(bad.score, 0.0)

    def test_promotion_requires_gain_without_regression(self) -> None:
        base = CandidateScore("base", 0.70, 0.66, 1.0, 0, tuple())
        better = CandidateScore("better", 0.82, 1.0, 1.1, 0, tuple())
        unsafe = CandidateScore("unsafe", 0.95, 1.0, 0.5, 1, tuple())
        self.assertTrue(ModelTournament.promotion(better, base, 0.05).promote)
        self.assertFalse(ModelTournament.promotion(unsafe, base, 0.05).promote)

    def test_trajectory_miner_requires_repetition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrajectoryStore(Path(tmp) / "t.db")
            store.record("s", "prepare twitch stream", "m", "success", 1.0, "ok")
            store.record("s", "prepare twitch stream", "m", "success", 0.9, "ok")
            proposals = TrajectoryMiner(store).proposals(min_samples=2)
            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0].sample_count, 2)
            store.close()


if __name__ == "__main__":
    unittest.main()
