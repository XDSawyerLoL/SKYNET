import tempfile
import unittest
from pathlib import Path

from skynet.delegation import CapabilityLeaseStore
from skynet.identity import LocalIdentityStore


class DelegationTests(unittest.TestCase):
    def test_lease_is_signed_bound_and_budgeted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = LocalIdentityStore(root / "identity.key")
            store = CapabilityLeaseStore(root / "leases.json", identity)
            lease = store.issue("agent-b", ["research"], "policy-123", ttl_seconds=60, max_calls=1)
            self.assertTrue(store.verify(lease.lease_id, "research", "agent-b", "policy-123")[0])
            self.assertFalse(store.verify(lease.lease_id, "execute", "agent-b", "policy-123")[0])
            self.assertTrue(store.consume(lease.lease_id, "research", "agent-b", "policy-123")[0])
            self.assertFalse(store.verify(lease.lease_id, "research", "agent-b", "policy-123")[0])

    def test_revoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = LocalIdentityStore(root / "identity.key")
            store = CapabilityLeaseStore(root / "leases.json", identity)
            lease = store.issue("agent-b", ["*"], "policy-123")
            self.assertTrue(store.revoke(lease.lease_id))
            self.assertFalse(store.verify(lease.lease_id, "anything", "agent-b", "policy-123")[0])


if __name__ == "__main__":
    unittest.main()
