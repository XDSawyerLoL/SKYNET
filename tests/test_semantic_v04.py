import tempfile
import unittest
from pathlib import Path

from skynet.semantic import SemanticMemory


class SemanticMemoryV04Tests(unittest.TestCase):
    def test_local_semantic_retrieval_without_embedding_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SemanticMemory(Path(tmp) / "semantic.db")
            store.add("OBS stream setup with scenes and Twitch dashboard", source="skill")
            store.add("Recipe for tomato soup", source="note")
            results = store.search("prepare twitch stream in OBS", limit=2)
            self.assertEqual(results[0][1], "skill")
            self.assertIn("OBS", results[0][2])
            store.close()


if __name__ == "__main__":
    unittest.main()
