import unittest

from skynet.routing import ModelRouter


class ModelRouterTests(unittest.TestCase):
    def test_coder_model_is_preferred_for_code(self):
        router = ModelRouter(
            "http://127.0.0.1:11434",
            "qwen3:8b",
            ["qwen3:8b", "qwen2.5-coder:7b"],
        )
        decision = router.decide(
            "Corrige ce bug Python dans mon script",
            ["qwen3:8b", "qwen2.5-coder:7b"],
        )
        self.assertEqual(decision.model, "qwen2.5-coder:7b")

    def test_default_is_used_when_only_default_is_available(self):
        router = ModelRouter("http://127.0.0.1:11434", "qwen3:8b", ["qwen3:8b", "coder:7b"])
        decision = router.decide("analyse cette situation", ["qwen3:8b"])
        self.assertEqual(decision.model, "qwen3:8b")

    def test_unconfigured_installed_model_is_used_as_local_fallback(self):
        router = ModelRouter("http://127.0.0.1:11434", "qwen3:8b", ["qwen3:8b"])
        decision = router.decide("bonjour", ["gemma3:4b"])
        self.assertEqual(decision.model, "gemma3:4b")
        self.assertIn("locally installed", decision.reason)

    def test_measured_preferred_model_wins_general_task(self):
        router = ModelRouter("http://127.0.0.1:11434", "base:8b", ["base:8b", "candidate:8b"])
        router.configure_deployment("candidate:8b", "active")
        decision = router.decide("résume ce document", ["base:8b", "candidate:8b"])
        self.assertEqual(decision.model, "candidate:8b")
        self.assertIn("measured preferred", decision.reason)

    def test_canary_routing_is_deterministic(self):
        router = ModelRouter("http://127.0.0.1:11434", "base:8b", ["base:8b", "candidate:8b"])
        router.configure_deployment("candidate:8b", "canary", canary_ratio=0.5)
        first = router.decide("same exact prompt", ["base:8b", "candidate:8b"])
        second = router.decide("same exact prompt", ["base:8b", "candidate:8b"])
        self.assertEqual(first.model, second.model)
        self.assertEqual(first.reason, second.reason)


if __name__ == "__main__":
    unittest.main()
