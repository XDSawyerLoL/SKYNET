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


if __name__ == "__main__":
    unittest.main()
