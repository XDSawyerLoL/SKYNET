import unittest

from skynet.ui import orb_mode


class DesktopUiStateTests(unittest.TestCase):
    def test_orb_state_priority(self):
        self.assertEqual(orb_mode(busy=False, autonomy_busy=False, stopped=False), "idle")
        self.assertEqual(orb_mode(busy=True, autonomy_busy=False, stopped=False), "thinking")
        self.assertEqual(orb_mode(busy=False, autonomy_busy=True, stopped=False), "acting")
        self.assertEqual(orb_mode(busy=True, autonomy_busy=True, stopped=True), "stopped")


if __name__ == "__main__":
    unittest.main()
