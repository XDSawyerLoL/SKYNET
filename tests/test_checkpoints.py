import tempfile
import unittest
from pathlib import Path

from skynet.checkpoints import CheckpointStore


class CheckpointStoreTests(unittest.TestCase):
    def test_latest_checkpoint_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.db"
            store = CheckpointStore(path)
            store.save("routine", "abc", "running", {"step": 1})
            store.save("routine", "abc", "failed", {"error": "boom"})
            self.assertEqual(store.latest("routine", "abc").status, "failed")
            store.close()

            reopened = CheckpointStore(path)
            latest = reopened.latest("routine", "abc")
            self.assertIsNotNone(latest)
            self.assertEqual(latest.state["error"], "boom")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
