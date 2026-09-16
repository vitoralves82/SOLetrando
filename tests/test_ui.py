import unittest

from soletrando_ui import StatusOverlay


class StatusOverlayTests(unittest.TestCase):
    def test_state_command_preserves_timeout_and_force_show(self):
        overlay = StatusOverlay(320, 110)
        overlay.set_state("preview", "Exemplo", hide_after=1.0, force_show=True)
        self.assertEqual(
            overlay._commands.get_nowait(),
            ("state", "preview", "Exemplo", 1.0, True),
        )

    def test_resize_and_hide_commands(self):
        overlay = StatusOverlay()
        overlay.configure(220, 76)
        overlay.hide()
        self.assertEqual(overlay._commands.get_nowait(), ("configure", 220, 76))
        self.assertEqual(overlay._commands.get_nowait(), ("hide",))


if __name__ == "__main__":
    unittest.main()
