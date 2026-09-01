from pathlib import Path
import tempfile
import unittest

from skynet.audit import AuditLog
from skynet.memory import MemoryStore
from skynet.permissions import PermissionGate
from skynet.skills import SkillStore
from skynet.tools import ToolBus, ToolError


class ToolBusTests(unittest.TestCase):
    def _bus(self, root: Path) -> tuple[ToolBus, MemoryStore]:
        memory = MemoryStore(root / "data" / "memory.db")
        bus = ToolBus(
            workspace=root / "workspace",
            memory=memory,
            skills=SkillStore(root / "data" / "skills"),
            audit=AuditLog(root / "data" / "audit.jsonl"),
            permissions=PermissionGate(),
        )
        return bus, memory

    def test_workspace_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bus, memory = self._bus(Path(tmp))
            with self.assertRaises(ToolError):
                bus._resolve("../outside.txt")
            memory.close()

    def test_write_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bus, memory = self._bus(Path(tmp))
            denied = bus.execute("write_file", {"path": "a.txt", "content": "x"}, lambda _: False)
            self.assertIn("DENIED", denied)
            self.assertFalse((Path(tmp) / "workspace" / "a.txt").exists())

            allowed = bus.execute("write_file", {"path": "a.txt", "content": "x"}, lambda _: True)
            self.assertIn("Wrote", allowed)
            self.assertEqual((Path(tmp) / "workspace" / "a.txt").read_text(encoding="utf-8"), "x")
            memory.close()


if __name__ == "__main__":
    unittest.main()
