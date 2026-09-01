import tempfile
import unittest
from pathlib import Path

from skynet.interop import AgentCard, AgentRegistry, DelegatedTask


class InteropV04Tests(unittest.TestCase):
    def test_agent_registry_and_delegation_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistry(Path(tmp) / "agents.json")
            registry.register(AgentCard("coder", "agent:coder", capabilities=["code", "review"]))
            found = registry.find_capability("code")
            self.assertEqual(found[0].agent_id, "agent:coder")
            task = DelegatedTask.create("agent:root", "agent:coder", "Review code", "abc")
            self.assertEqual(task.status, "submitted")
            self.assertEqual(task.mandate_hash, "abc")


if __name__ == "__main__":
    unittest.main()
