import unittest

from soletrando_config import (
    DEFAULT_CONFIG,
    describe_config_for_log,
    sanitize_config,
)


class SanitizeConfigTests(unittest.TestCase):
    def test_existing_user_choices_are_preserved(self):
        saved = {
            "hotkey_toggle": "f9",
            "model": "large-v3",
            "language": "pt",
            "insert_mode": "type",
            "vocabulary": ["EnvironPact"],
            "corrections": {"pro clima": "PROCLIM"},
            "save_history": False,
            "overlay_width": 400,
        }
        config = sanitize_config(saved)
        for key, value in saved.items():
            self.assertEqual(config[key], value, key)

    def test_config_from_previous_version_receives_new_defaults(self):
        config = sanitize_config({"model": "large-v3", "hotkey_toggle": "f8"})
        self.assertEqual(config["hotkey_read"], DEFAULT_CONFIG["hotkey_read"])
        self.assertEqual(config["speech_rate"], 0)
        self.assertTrue(config["clipboard_private"])

    def test_invalid_values_fall_back_to_defaults(self):
        config = sanitize_config({
            "hotkey_toggle": "tecla inexistente",
            "hotkey_read": "ctrl+alt+inexistente",
            "model": "gigante",
            "speech_rate": "rapido",
            "clipboard_private": "sim",
            "overlay_width": "largo",
        })
        self.assertEqual(config["hotkey_toggle"], DEFAULT_CONFIG["hotkey_toggle"])
        self.assertEqual(config["hotkey_read"], DEFAULT_CONFIG["hotkey_read"])
        self.assertEqual(config["model"], DEFAULT_CONFIG["model"])
        self.assertEqual(config["speech_rate"], 0)
        self.assertTrue(config["clipboard_private"])
        self.assertEqual(config["overlay_width"], DEFAULT_CONFIG["overlay_width"])

    def test_speech_voices_keep_only_valid_language_and_name(self):
        voices = sanitize_config({
            "speech_voices": {
                "pt": "  Microsoft Francisca (Natural) - Portuguese (Brazil) ",
                "en": "",
                "es": "Voz\ncom quebra",
                "fr": "Microsoft Hortense",
                "xx": 3,
            }
        })["speech_voices"]
        self.assertEqual(
            voices, {"pt": "Microsoft Francisca (Natural) - Portuguese (Brazil)"}
        )
        self.assertEqual(sanitize_config({"speech_voices": "Maria"})["speech_voices"], {})
        self.assertEqual(sanitize_config({})["speech_voices"], {})

    def test_speech_rate_is_limited_to_windows_range(self):
        self.assertEqual(sanitize_config({"speech_rate": 25})["speech_rate"], 10)
        self.assertEqual(sanitize_config({"speech_rate": -25})["speech_rate"], -10)
        self.assertEqual(sanitize_config({"speech_rate": True})["speech_rate"], 0)

    def test_reading_hotkey_is_disabled_when_it_conflicts(self):
        config = sanitize_config({"hotkey_toggle": "pause", "hotkey_read": "pause"})
        self.assertEqual(config["hotkey_toggle"], "pause")
        self.assertEqual(config["hotkey_read"], "")

    def test_reading_hotkey_can_be_disabled(self):
        self.assertEqual(sanitize_config({"hotkey_read": ""})["hotkey_read"], "")

    def test_default_reading_hotkey_and_previous_choice_is_kept(self):
        self.assertEqual(sanitize_config({})["hotkey_read"], "ctrl+alt+a")
        # Quem ja salvou Ctrl+Alt+L continua com a escolha anterior.
        self.assertEqual(
            sanitize_config({"hotkey_read": "ctrl+alt+l"})["hotkey_read"],
            "ctrl+alt+l",
        )


class ConfigLogTests(unittest.TestCase):
    def test_log_summary_omits_vocabulary_and_corrections(self):
        config = sanitize_config({
            "vocabulary": ["Cliente Sigiloso", "Projeto Netuno"],
            "corrections": {"joao da silva": "João da Silva"},
        })
        summary = describe_config_for_log(config)
        for private in ("Sigiloso", "Netuno", "joao", "João"):
            self.assertNotIn(private, summary)
        self.assertIn("vocabulario=2 termo(s)", summary)
        self.assertIn("correcoes=1 regra(s)", summary)
        self.assertIn("model='large-v3-turbo'", summary)

    def test_unknown_keys_are_not_logged(self):
        summary = describe_config_for_log({"campo_futuro": "dado pessoal"})
        self.assertNotIn("dado pessoal", summary)


if __name__ == "__main__":
    unittest.main()
