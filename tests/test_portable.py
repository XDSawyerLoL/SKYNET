from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from skynet import portable_entry


class PortableEntryTests(unittest.TestCase):
    def test_source_mode_uses_current_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            try:
                os.chdir(tmp)
                self.assertEqual(portable_entry.portable_root(), Path(tmp).resolve())
            finally:
                os.chdir(previous)

    def test_prepare_portable_environment_sets_relative_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            keys = ("SKYNET_PORTABLE", "SKYNET_DATA_DIR", "SKYNET_WORKSPACE", "SKYNET_MCP_CONFIG")
            saved = {key: os.environ.get(key) for key in keys}
            try:
                for key in keys:
                    os.environ.pop(key, None)
                os.chdir(tmp)
                root = portable_entry.prepare_portable_environment()
                self.assertEqual(root, Path(tmp).resolve())
                self.assertEqual(os.environ["SKYNET_PORTABLE"], "1")
                self.assertEqual(os.environ["SKYNET_DATA_DIR"], ".skynet")
                self.assertEqual(os.environ["SKYNET_WORKSPACE"], "workspace")
                self.assertEqual(os.environ["SKYNET_MCP_CONFIG"], ".skynet/mcp.json")
            finally:
                os.chdir(previous)
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
