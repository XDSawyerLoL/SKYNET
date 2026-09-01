from pathlib import Path
import tempfile
import time
import unittest

from skynet.browser import BrowserError, BrowserHarness
from skynet.channels import ChannelHub
from skynet.integrations import IntegrationRegistry
from skynet.memory import MemoryStore
from skynet.permissions import PermissionGate, PermissionLevel
from skynet.scheduler import RoutineStore
from skynet.sessions import SessionStore
from skynet.skills import SkillStore
from skynet.swarm import AgentTask, SwarmEngine


class ProductConvergenceTests(unittest.TestCase):
    def test_sessions_search_and_fork_persist_history(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "memory.db"
            memory = MemoryStore(db)
            sessions = SessionStore(db)
            sessions.ensure("alpha", title="Alpha", project="SKYNET")
            memory.add_message("alpha", "user", "diagnostic browser unique-needle")
            memory.add_message("alpha", "assistant", "evidence captured")
            hits = sessions.search("unique-needle")
            self.assertEqual(hits[0]["session_id"], "alpha")
            fork = sessions.fork("alpha", title="Forked")
            copied = memory.recent_messages(fork.session_id, 10)
            self.assertEqual(len(copied), 2)
            self.assertEqual(fork.project, "SKYNET")
            sessions.close(); memory.close()

    def test_integration_registry_is_declarative_and_capability_indexed(self):
        with tempfile.TemporaryDirectory() as td:
            registry = IntegrationRegistry(Path(td) / "integrations.json")
            registry.seed_builtin("core:test", ["alpha", "beta"])
            registry.discover_mcp(["github"])
            enabled = registry.list(enabled_only=True)
            self.assertEqual({x.name for x in enabled}, {"core:test", "mcp:github"})
            index = registry.capability_index()
            self.assertIn("core:test", index["alpha"])
            self.assertIn("mcp:github", index["dynamic-tools"])

    def test_channel_bus_persists_inbox_and_outbox(self):
        with tempfile.TemporaryDirectory() as td:
            hub = ChannelHub(Path(td) / "channels.db")
            inbound = hub.receive("discord", "peer-1", "hello", "discord:peer-1")
            self.assertEqual(hub.pending()[0].message_id, inbound.message_id)
            hub.mark(inbound.message_id, "processed")
            outbound = hub.send("discord", "peer-1", "reply", "discord:peer-1")
            self.assertEqual(hub.outbox()[0].message_id, outbound.message_id)
            hub.close()

    def test_skills_progressive_disclosure_supports_external_skill_md(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            internal = root / "skills"
            external = root / "external" / "browser-recovery"
            external.mkdir(parents=True)
            (external / "SKILL.md").write_text(
                "# Browser recovery\n\nPurpose: recover browser navigation failures.\nSteps: inspect snapshot and verify URL.\n",
                encoding="utf-8",
            )
            store = SkillStore(internal, external_paths=[external.parent])
            matches = store.search("browser navigation recovery")
            self.assertTrue(matches)
            self.assertEqual(matches[0].name, "browser-recovery")
            context = store.context_for("recover browser navigation", limit=1)
            self.assertIn("inspect snapshot", context[0][1])
            self.assertEqual(store.usage()[0]["uses"], 1)
            store.close()

    def test_automation_can_bind_session_and_run_once(self):
        with tempfile.TemporaryDirectory() as td:
            store = RoutineStore(Path(td) / "routines.db")
            item = store.create_once("followup", "check result", time.time() + 1, session_id="project:42")
            self.assertEqual(item.session_id, "project:42")
            self.assertEqual(item.trigger, "once")
            store.mark_result(item.id, "ok", now=item.next_run)
            current = store.get(item.id)
            self.assertFalse(current.enabled)
            self.assertEqual(current.run_count, 1)
            store.close()

    def test_swarm_dependency_graph_rejects_cycles_before_model_calls(self):
        tasks = [AgentTask("a", "analyst", "a", ("b",)), AgentTask("b", "critic", "b", ("a",))]
        with self.assertRaises(ValueError):
            SwarmEngine._validate_graph(tasks)

    def test_browser_rejects_non_http_urls(self):
        with tempfile.TemporaryDirectory() as td:
            browser = BrowserHarness(Path(td))
            with self.assertRaises(BrowserError):
                browser.navigate("file:///etc/passwd")
            self.assertIn(browser.state().mode, {"http-readonly", "playwright-local"})
            browser.close()

    def test_new_tools_keep_explicit_permission_classes(self):
        gate = PermissionGate()
        self.assertEqual(gate.level_for("session_search"), PermissionLevel.OBSERVE)
        self.assertEqual(gate.level_for("browser_navigate"), PermissionLevel.SAFE)
        self.assertEqual(gate.level_for("browser_type"), PermissionLevel.CONFIRM)
        self.assertEqual(gate.level_for("dev_run_tests"), PermissionLevel.CONFIRM)


if __name__ == "__main__":
    unittest.main()
