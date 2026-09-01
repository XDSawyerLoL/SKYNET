from pathlib import Path
import tempfile
import unittest

from skynet.runtime import Runtime


class RuntimeV09Tests(unittest.TestCase):
    def test_runtime_exposes_product_convergence_layers_without_ollama_call(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runtime = Runtime.create(root, session_id="smoke")
            try:
                names = {schema["function"]["name"] for schema in runtime.tools.schemas()}
                self.assertIn("session_search", names)
                self.assertIn("browser_navigate", names)
                self.assertIn("dev_git_status", names)
                self.assertIn("integration_list", names)
                self.assertIn("swarm_analyze", names)
                self.assertEqual(runtime.sessions.get("smoke").session_id, "smoke")
                enabled = {x.name for x in runtime.integrations.list(enabled_only=True)}
                self.assertIn("core:ollama", enabled)
                self.assertIn("core:browser", enabled)
                self.assertTrue(runtime.channels.recent(5) == [])
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
