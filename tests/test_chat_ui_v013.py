from __future__ import annotations

import unittest


class ConversationFirstV013Tests(unittest.TestCase):
    def test_chat_desktop_imports(self) -> None:
        import skynet.desktop_chat as desktop_chat
        self.assertTrue(callable(desktop_chat.main))
        self.assertTrue(hasattr(desktop_chat, "ChatWindow"))
        self.assertIn("Message à SKYNET", desktop_chat.ChatWindow._build_main.__code__.co_consts)

    def test_agentic_escalation_keeps_small_talk_fast(self) -> None:
        from skynet.agent import Agent
        self.assertFalse(Agent.requires_agentic_mode("Salut, comment vas-tu ?"))
        self.assertFalse(Agent.requires_agentic_mode("Explique-moi simplement la relativité."))
        self.assertTrue(Agent.requires_agentic_mode("Ouvre le navigateur et cherche sur le web."))
        self.assertTrue(Agent.requires_agentic_mode("Corrige le code de ce projet GitHub."))

    def test_ollama_client_keeps_model_warm(self) -> None:
        from skynet.ollama import OllamaClient
        client = OllamaClient("http://127.0.0.1:11434", "qwen3:8b")
        self.assertEqual(client.keep_alive, "30m")
        self.assertTrue(callable(client.chat_stream))
        self.assertTrue(callable(client.warm))


if __name__ == "__main__":
    unittest.main()
