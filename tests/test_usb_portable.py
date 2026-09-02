from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from skynet.usb_entry import MODEL_FILE, find_llama_server, usb_layout
from skynet.usb_proxy import (
    USB_MODEL,
    ollama_message_from_openai,
    openai_payload_from_ollama,
    stream_event_from_openai,
    tags_payload,
)


class USBPortableTests(unittest.TestCase):
    def test_layout_keeps_model_engine_and_state_beside_usb_root(self) -> None:
        root = Path("C:/SKYNET-USB")
        layout = usb_layout(root)
        self.assertEqual(layout["model"].name, MODEL_FILE)
        self.assertEqual(layout["model"].parent.name, "models")
        self.assertEqual(layout["vulkan"].name, "vulkan")
        self.assertEqual(layout["cpu"].name, "cpu")
        self.assertEqual(layout["data"].name, ".skynet")
        self.assertEqual(layout["workspace"].name, "workspace")

    def test_find_llama_server_supports_nested_release_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "release" / "bin"
            nested.mkdir(parents=True)
            target = nested / "llama-server.exe"
            target.write_bytes(b"MZ")
            self.assertEqual(find_llama_server(root), target)

    def test_tags_exposes_bundled_model(self) -> None:
        payload = tags_payload()
        self.assertEqual(payload["models"][0]["name"], USB_MODEL)
        self.assertEqual(payload["models"][0]["details"]["quantization_level"], "Q4_K_M")

    def test_ollama_request_becomes_openai_request_and_disables_thinking(self) -> None:
        payload = openai_payload_from_ollama({
            "model": USB_MODEL,
            "stream": False,
            "messages": [{"role": "user", "content": "Bonjour"}],
            "tools": [{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}],
            "options": {"num_predict": 120},
        })
        self.assertEqual(payload["model"], USB_MODEL)
        self.assertIn("/no_think", payload["messages"][-1]["content"])
        self.assertEqual(payload["max_tokens"], 120)
        self.assertEqual(payload["tool_choice"], "auto")

    def test_non_stream_message_preserves_tool_calls(self) -> None:
        source = {
            "choices": [{"message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "x", "type": "function", "function": {"name": "demo", "arguments": "{}"}}],
            }}]
        }
        message = ollama_message_from_openai(source)
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "demo")

    def test_stream_delta_becomes_ollama_ndjson_event(self) -> None:
        event = stream_event_from_openai({"choices": [{"delta": {"content": "Salut"}}]})
        self.assertIsNotNone(event)
        self.assertEqual(event["message"]["content"], "Salut")
        self.assertFalse(event["done"])
        self.assertIsNone(stream_event_from_openai({"choices": [{"delta": {}}]}))


if __name__ == "__main__":
    unittest.main()
