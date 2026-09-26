import unittest

from soletrando_ui import (
    StatusOverlay,
    choices_with_current,
    validate_settings,
)


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


class SettingsHelpersTests(unittest.TestCase):
    def valid_values(self, **changes):
        values = {
            "hotkey_toggle": "scroll lock",
            "hotkey_quit": "ctrl+shift+q",
            "hotkey_read": "ctrl+alt+l",
            "overlay_width": 320,
            "overlay_height": 110,
        }
        values.update(changes)
        return values

    def test_current_value_outside_options_is_kept(self):
        options = [("Português", "pt"), ("Inglês", "en")]
        self.assertEqual(choices_with_current(options, "pt"), options)
        self.assertEqual(
            choices_with_current(options, "fr", "Outro")[-1], ("Outro (fr)", "fr")
        )

    def test_valid_settings_pass(self):
        self.assertIsNone(validate_settings(self.valid_values()))
        self.assertIsNone(validate_settings(self.valid_values(hotkey_read="")))

    def test_reading_key_cannot_repeat_recording_or_quit_key(self):
        problem = validate_settings(
            self.valid_values(hotkey_toggle="pause", hotkey_read="pause")
        )
        self.assertEqual(problem[0], "reading")
        problem = validate_settings(
            self.valid_values(hotkey_read="ctrl+shift+q")
        )
        self.assertEqual(problem[0], "reading")

    def test_overlay_size_must_be_within_limits(self):
        self.assertEqual(
            validate_settings(self.valid_values(overlay_width=50))[0], "overlay"
        )
        self.assertEqual(
            validate_settings(self.valid_values(overlay_height=None))[0], "overlay"
        )


if __name__ == "__main__":
    unittest.main()
