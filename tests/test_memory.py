from pathlib import Path
import tempfile
import unittest

from skynet.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_messages_and_memories_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            store = MemoryStore(path)
            store.add_message("s", "user", "hello")
            store.remember("likes local models")
            store.close()

            reopened = MemoryStore(path)
            self.assertEqual(reopened.recent_messages("s"), [{"role": "user", "content": "hello"}])
            self.assertEqual(reopened.list_memories(), ["likes local models"])
            reopened.close()


if __name__ == "__main__":
    unittest.main()
