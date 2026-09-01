import tempfile
import time
import unittest
from pathlib import Path

from skynet.scheduler import RoutineStore


class RoutineStoreTests(unittest.TestCase):
    def test_due_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "routines.db"
            store = RoutineStore(path)
            item = store.create("health", "inspect local status", 60, start_in_seconds=0)
            self.assertEqual(store.due(limit=5)[0].id, item.id)
            store.mark_result(item.id, "ok", now=time.time())
            self.assertEqual(store.due(limit=5), [])
            store.close()

            reopened = RoutineStore(path)
            loaded = reopened.get(item.id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.last_status, "ok")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
