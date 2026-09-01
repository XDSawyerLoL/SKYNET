from __future__ import annotations

import unittest

import skynet
from skynet.desktop_premium import NAV_ITEMS, _field
from skynet.ui_premium import PALETTE


class PremiumUITests(unittest.TestCase):
    def test_release_version(self) -> None:
        self.assertEqual(skynet.__version__, "0.11.0")

    def test_navigation_surface_contains_core_product_sections(self) -> None:
        names = {key for key, _icon, _label in NAV_ITEMS}
        self.assertTrue({"home", "chat", "memory", "skills", "automations", "browser", "integrations", "devices", "sessions", "system"}.issubset(names))

    def test_field_supports_dict_and_object(self) -> None:
        self.assertEqual(_field({"name": "alpha"}, "name"), "alpha")

        class Item:
            name = "beta"

        self.assertEqual(_field(Item(), "name"), "beta")

    def test_palette_keeps_dark_command_center_identity(self) -> None:
        self.assertTrue(PALETTE.bg.startswith("#"))
        self.assertNotEqual(PALETTE.bg, PALETTE.cyan)
        self.assertNotEqual(PALETTE.panel, PALETTE.text)


if __name__ == "__main__":
    unittest.main()
