import tempfile
import unittest
from pathlib import Path

from skynet.trajectories import TrajectoryStore


class TrajectoryV04Tests(unittest.TestCase):
    def test_successful_trajectory_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trajectories.db"
            store = TrajectoryStore(path)
            store.record("s1", "Fix build", "qwen3:8b", "success", 0.9, "tests green", {"tool_calls": 3})
            store.close()
            reopened = TrajectoryStore(path)
            best = reopened.best(5)
            self.assertEqual(best[0]["goal"], "Fix build")
            self.assertEqual(best[0]["metadata"]["tool_calls"], 3)
            reopened.close()


if __name__ == "__main__":
    unittest.main()
