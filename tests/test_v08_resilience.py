import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from skynet.backup import BackupManager
from skynet.governance import GovernedToolBus
from skynet.health import CrashLoopGuard, GlobalControl, HeartbeatStore
from skynet.identity import LocalIdentityStore
from skynet.policy import MandateStore, PolicyEngine, ReceiptStore
from skynet.regression import FailureRegressionSuite, RegressionCase
from skynet.trust import ValidationCheck, ValidationReportStore


class _DummyInner:
    def __init__(self):
        self.called = False

    def schemas(self):
        return []

    def execute(self, name, args, confirmer):
        self.called = True
        return "SHOULD NOT RUN"


class V08ResilienceTests(unittest.TestCase):
    def test_kill_switch_requires_explicit_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            control = GlobalControl(Path(tmp) / "kill.json")
            self.assertFalse(control.engaged())
            control.engage("test")
            self.assertTrue(control.engaged())
            self.assertEqual(control.status()["reason"], "test")
            control.release()
            self.assertFalse(control.engaged())

    def test_kill_switch_blocks_below_model_before_inner_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = LocalIdentityStore(root / "identity.key")
            receipts = ReceiptStore(root / "receipts.db", identity)
            mandates = MandateStore(root / "mandate.json", identity.identity.agent_id)
            policy = PolicyEngine(receipts)
            control = GlobalControl(root / "kill.json")
            control.engage("test")
            inner = _DummyInner()
            bus = GovernedToolBus(inner, mandates, policy, receipts, identity.identity.agent_id, control=control)
            result = bus.execute("read_file", {"path": "x.txt"}, lambda _: True)
            self.assertTrue(result.startswith("DENIED BY GLOBAL KILL SWITCH"))
            self.assertFalse(inner.called)
            receipts.close()

    def test_heartbeat_staleness(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = HeartbeatStore(Path(tmp) / "heartbeats.json")
            store.beat("worker", "ok", pid=123)
            self.assertFalse(store.stale("worker", 60))
            data = json.loads((Path(tmp) / "heartbeats.json").read_text(encoding="utf-8"))
            data["worker"]["timestamp"] = time.time() - 120
            (Path(tmp) / "heartbeats.json").write_text(json.dumps(data), encoding="utf-8")
            self.assertTrue(store.stale("worker", 60))

    def test_crash_loop_guard_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            guard = CrashLoopGuard(Path(tmp) / "crashes.json", max_crashes=3, window_s=300)
            self.assertFalse(guard.blocked())
            guard.record_crash(); guard.record_crash(); guard.record_crash()
            self.assertTrue(guard.blocked())
            guard.reset()
            self.assertFalse(guard.blocked())

    def test_validation_report_signature_detects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = LocalIdentityStore(root / "identity.key")
            reports = ValidationReportStore(root / "reports", identity)
            report = reports.create(
                "candidate-a", "basehash", "candidatehash",
                [ValidationCheck("static", True, "ok")],
            )
            self.assertTrue(report.passed)
            self.assertTrue(reports.verify(report))
            tampered = replace(report, candidate_hash="evil")
            self.assertFalse(reports.verify(tampered))

    def test_portable_backup_excludes_identity_and_restores_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            (data / "identity.key").write_text("secret-identity", encoding="utf-8")
            (data / "memory.db").write_bytes(b"memory-state")
            (data / "skills").mkdir()
            (data / "skills" / "a.md").write_text("skill", encoding="utf-8")
            manager = BackupManager(data, data / "backups")
            exported = manager.export_portable("portable.zip")
            target = root / "restored"
            target.mkdir()
            restore = BackupManager(target, target / "backups")
            count = restore.import_portable(Path(exported.path))
            self.assertGreaterEqual(count, 2)
            self.assertEqual((target / "memory.db").read_bytes(), b"memory-state")
            self.assertFalse((target / "identity.key").exists())

    def test_failure_regression_scoring_rejects_false_success(self):
        case = RegressionCase("x", 1, "prompt", ("mission accomplished",), ("verify", "evidence"))
        good = FailureRegressionSuite.score(case, "We must verify current state and gather evidence.")
        bad = FailureRegressionSuite.score(case, "Mission accomplished.")
        self.assertTrue(good.passed)
        self.assertFalse(bad.passed)


if __name__ == "__main__":
    unittest.main()
