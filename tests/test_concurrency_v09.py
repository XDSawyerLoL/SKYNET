from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import tempfile
import unittest

from skynet.audit import AuditLog
from skynet.channels import ChannelHub
from skynet.checkpoints import CheckpointStore
from skynet.memory import MemoryStore
from skynet.scheduler import RoutineStore
from skynet.sessions import SessionStore
from skynet.semantic import SemanticMemory
from skynet.skills import SkillStore
from skynet.trajectories import TrajectoryStore


class ConcurrencyV09Tests(unittest.TestCase):
    def test_runtime_stores_accept_cross_thread_operations(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = MemoryStore(root / "memory.db")
            sessions = SessionStore(root / "memory.db")
            semantic = SemanticMemory(root / "semantic.db")
            trajectories = TrajectoryStore(root / "trajectories.db")
            skills = SkillStore(root / "skills")
            channels = ChannelHub(root / "channels.db")
            checkpoints = CheckpointStore(root / "checkpoints.db")
            routines = RoutineStore(root / "routines.db")
            audit = AuditLog(root / "audit.jsonl")

            def work(i: int) -> None:
                sid = f"s{i}"
                sessions.ensure(sid, title=f"Session {i}")
                memory.add_message(sid, "user", f"message {i}")
                semantic.add(f"semantic {i}", source=sid)
                trajectories.record(sid, f"goal {i}", "fake", "success", 1.0, f"evidence {i}")
                channels.receive("test", str(i), f"channel {i}", sid)
                checkpoints.save("test", sid, "ok", {"i": i})
                routines.create(f"r{i}", f"routine {i}", 60, session_id=sid, max_runs=1)
                audit.record("test", {"i": i}, "ok")

            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(work, range(12)))

            self.assertEqual(len(sessions.list(limit=100)), 12)
            self.assertEqual(len(channels.pending(limit=100)), 12)
            self.assertEqual(len(checkpoints.recent(100)), 12)
            self.assertEqual(len(routines.list()), 12)
            self.assertEqual(len(trajectories.recent(100)), 12)
            self.assertEqual(len(memory.recent_messages("s3", 10)), 1)
            self.assertTrue(semantic.search("semantic 3", 3))

            lines = [json.loads(x) for x in (root / "audit.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(lines), 12)
            previous = "GENESIS"
            for event in lines:
                self.assertEqual(event["previous_hash"], previous)
                previous = event["hash"]

            routines.close(); checkpoints.close(); channels.close(); skills.close()
            trajectories.close(); semantic.close(); sessions.close(); memory.close()


if __name__ == "__main__":
    unittest.main()
