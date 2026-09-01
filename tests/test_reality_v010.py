from pathlib import Path
import tempfile
import unittest

from skynet.channels import ChannelHub
from skynet.reality import RealityAccelerator, ShadowTrajectoryAnalyzer
from skynet.trajectories import TrajectoryStore


class RealityV010Tests(unittest.TestCase):
    def test_channel_delivery_is_idempotent_across_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "channels.db"
            hub = ChannelHub(path)
            first = hub.receive("discord", "peer", "hello", "session", dedupe_key="event-42")
            duplicate = hub.receive("discord", "peer", "hello", "session", dedupe_key="event-42")
            self.assertEqual(first.message_id, duplicate.message_id)
            hub.close()

            reopened = ChannelHub(path)
            after_restart = reopened.receive("discord", "peer", "hello", "session", dedupe_key="event-42")
            self.assertEqual(first.message_id, after_restart.message_id)
            reopened.close()

    def test_accelerator_runs_real_core_components_without_failures(self):
        with tempfile.TemporaryDirectory() as td:
            accelerator = RealityAccelerator(Path(td) / "reports", seed=1234)
            report = accelerator.run(episodes=64, workers=4, virtual_minutes_per_episode=60)
            self.assertEqual(report.episodes, 64)
            self.assertEqual(report.virtual_hours, 64.0)
            self.assertEqual(report.failed_episodes, 0, report.failures)
            self.assertEqual(report.pass_rate, 1.0)
            self.assertGreater(report.operations, 500)
            self.assertTrue((Path(td) / "reports" / "latest.json").exists())

    def test_failures_can_be_promoted_into_regression_trajectory_store(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reports = root / "reports"
            reports.mkdir()
            (reports / "failures.jsonl").write_text(
                '{"episode":1,"fault":"replay_attack","invariant":"replay_protection","detail":"synthetic break"}\n',
                encoding="utf-8",
            )
            trajectories = TrajectoryStore(root / "trajectories.db")
            try:
                count = RealityAccelerator(reports).promote_failures(trajectories)
                self.assertEqual(count, 1)
                recent = trajectories.recent(10)
                self.assertEqual(recent[0]["outcome"], "failed")
                self.assertEqual(recent[0]["metadata"]["source"], "reality-accelerator")
            finally:
                trajectories.close()

    def test_shadow_analyzer_flags_false_success_language_without_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            trajectories = TrajectoryStore(Path(td) / "trajectories.db")
            try:
                trajectories.record(
                    "s1", "failed task", "fake", "failed", 0.0,
                    "Task completed successfully despite timeout", {"tool_calls": 2},
                )
                result = ShadowTrajectoryAnalyzer().analyze(trajectories, 10)
                self.assertEqual(result["analyzed"], 1)
                self.assertEqual(result["suspicious"], 1)
            finally:
                trajectories.close()


if __name__ == "__main__":
    unittest.main()
