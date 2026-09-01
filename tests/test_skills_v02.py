import tempfile
import unittest
from pathlib import Path

from skynet.skills import SkillStore


class SkillStoreV02Tests(unittest.TestCase):
    def test_save_and_read_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SkillStore(Path(tmp) / "skills")
            result = store.save_skill("prepare-stream", "# Prepare stream\n\n1. Open OBS.")
            self.assertIn("prepare-stream", result)
            self.assertTrue(store.read_skill("prepare-stream").startswith("# Prepare stream"))
            self.assertEqual(store.list_skills(), ["prepare-stream"])

    def test_reject_bad_skill_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SkillStore(Path(tmp) / "skills")
            with self.assertRaises(ValueError):
                store.save_skill("../escape", "nope")


if __name__ == "__main__":
    unittest.main()
