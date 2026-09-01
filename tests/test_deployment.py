import tempfile
import unittest
from pathlib import Path

from skynet.deployment import DeploymentRegistry


class DeploymentRegistryTests(unittest.TestCase):
    def test_promote_accept_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = DeploymentRegistry(Path(tmp) / "deployments.json")
            registry.promote("reasoning-model", "model-a", canary=False)
            canary = registry.promote("reasoning-model", "model-b", scorecard_id=7, canary=True)
            self.assertEqual(canary.previous, "model-a")
            self.assertEqual(canary.status, "canary")
            self.assertEqual(registry.accept_canary("reasoning-model").status, "active")
            rolled = registry.rollback("reasoning-model", "latency regression")
            self.assertEqual(rolled.active, "model-a")
            self.assertEqual(rolled.status, "rolled_back")


if __name__ == "__main__":
    unittest.main()
