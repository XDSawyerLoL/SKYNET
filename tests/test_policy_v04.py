import tempfile
import time
import unittest
from pathlib import Path

from skynet.identity import LocalIdentityStore
from skynet.policy import ActionRequest, Mandate, PolicyEngine, ReceiptStore
from skynet.policy_adapters import ERC8196Adapter


class PolicyV04Tests(unittest.TestCase):
    def test_policy_limits_and_receipt_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = LocalIdentityStore(root / "identity.key")
            receipts = ReceiptStore(root / "receipts.db", identity)
            engine = PolicyEngine(receipts)
            mandate = Mandate(
                mandate_id="m1",
                principal="owner",
                agent_id=identity.identity.agent_id,
                allowed_actions=["transfer"],
                allowed_targets=["merchant-a"],
                max_value_per_action=100,
                max_value_per_day=150,
                valid_after=time.time() - 10,
                valid_until=time.time() + 60,
                max_risk_score=20,
            )
            req = ActionRequest("transfer", identity.identity.agent_id, target="merchant-a", value=80, risk_score=10)
            decision = engine.evaluate(mandate, req)
            self.assertTrue(decision.allowed)
            receipts.append(req, decision, "ok")

            req2 = ActionRequest("transfer", identity.identity.agent_id, target="merchant-a", value=80, risk_score=10)
            self.assertEqual(engine.evaluate(mandate, req2).code, "daily_limit")
            self.assertTrue(receipts.verify_chain())
            receipts.close()

    def test_replay_and_erc_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = LocalIdentityStore(root / "identity.key")
            receipts = ReceiptStore(root / "receipts.db", identity)
            engine = PolicyEngine(receipts)
            mandate = Mandate("m2", "owner", identity.identity.agent_id, allowed_actions=["swap"])
            req = ActionRequest("swap", identity.identity.agent_id, nonce="same")
            decision = engine.evaluate(mandate, req)
            receipts.append(req, decision, "ok")
            replay = ActionRequest("swap", identity.identity.agent_id, nonce="same")
            self.assertEqual(engine.evaluate(mandate, replay).code, "replay")
            projection = ERC8196Adapter.compile(mandate)
            self.assertEqual(projection["standard"], "ERC-8196")
            self.assertEqual(projection["policyHash"], mandate.policy_hash)
            receipts.close()


if __name__ == "__main__":
    unittest.main()
