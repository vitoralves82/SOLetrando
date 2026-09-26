import json
import subprocess
import sys
import textwrap
import unittest

from soletrando_ui import (
    AUTO_VOICE_LABEL,
    StatusOverlay,
    choices_with_current,
    validate_settings,
    voice_choices,
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
            "hotkey_read": "ctrl+alt+a",
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

    def test_custom_hotkeys_are_validated_before_saving(self):
        values = self.valid_values(
            hotkey_toggle=" Alt + Ctrl + K ",
            hotkey_read="Ctrl + Shift + F12",
        )
        self.assertIsNone(validate_settings(values))
        self.assertEqual(values["hotkey_toggle"], "ctrl+alt+k")
        self.assertEqual(values["hotkey_read"], "ctrl+shift+f12")
        self.assertEqual(
            validate_settings(self.valid_values(hotkey_toggle="shift+k"))[0],
            "dictation",
        )
        function_keys = self.valid_values(hotkey_toggle="F9", hotkey_read="F12")
        self.assertIsNone(validate_settings(function_keys))
        self.assertEqual(function_keys["hotkey_toggle"], "f9")
        self.assertEqual(function_keys["hotkey_read"], "f12")

    def test_overlay_size_must_be_within_limits(self):
        self.assertEqual(
            validate_settings(self.valid_values(overlay_width=50))[0], "overlay"
        )
        self.assertEqual(
            validate_settings(self.valid_values(overlay_height=None))[0], "overlay"
        )


class VoiceChoicesTests(unittest.TestCase):
    VOICES = [
        {"name": "Microsoft Helia - Portuguese (Portugal)", "culture": "pt-PT"},
        {"name": "Microsoft Maria Desktop - Portuguese(Brazil)", "culture": "pt-BR"},
        {"name": "Microsoft Thalita Online (Natural) - Portuguese (Brazil)", "culture": "pt-BR"},
        {"name": "Microsoft Zira Desktop - English (United States)", "culture": "en-US"},
    ]

    def test_automatic_first_then_brazilian_voices(self):
        options = voice_choices(self.VOICES, "pt")
        self.assertEqual(options[0], (AUTO_VOICE_LABEL, ""))
        self.assertEqual(
            [value for _label, value in options[1:]],
            [
                "Microsoft Maria Desktop - Portuguese(Brazil)",
                "Microsoft Thalita Online (Natural) - Portuguese (Brazil)",
                "Microsoft Helia - Portuguese (Portugal)",
            ],
        )

    def test_online_voice_is_labelled(self):
        labels = [label for label, _value in voice_choices(self.VOICES, "pt")]
        self.assertIn(
            "Microsoft Thalita Online (Natural) - Portuguese (Brazil) (online)",
            labels,
        )

    def test_saved_voice_that_disappeared_stays_visible(self):
        options = voice_choices(self.VOICES, "pt", "Microsoft Francisca")
        self.assertEqual(
            options[-1],
            ("Microsoft Francisca (não encontrada)", "Microsoft Francisca"),
        )

    def test_saved_voice_is_kept_while_list_is_loading(self):
        self.assertEqual(
            voice_choices(None, "pt", "Microsoft Francisca"),
            [(AUTO_VOICE_LABEL, ""), ("Microsoft Francisca", "Microsoft Francisca")],
        )


@unittest.skipUnless(sys.platform == "win32", "Requer janelas do Windows")
class SettingsWindowTests(unittest.TestCase):
    def test_voice_and_rate_save_with_existing_overlay_root(self):
        script = textwrap.dedent('''
            import json
            import os
            import time
            import tkinter as tk
            from tkinter import ttk
            from soletrando_config import DEFAULT_CONFIG, MODEL_OPTIONS
            from soletrando_ui import show_settings_window

            overlay_root = tk.Tk()
            overlay_root.withdraw()
            original_tk = tk.Tk
            chosen_voice = "Microsoft Francisca (Natural) - Portuguese (Brazil)"
            saved = []
            windows = []

            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)

            def settings_root(*args, **kwargs):
                root = original_tk(*args, **kwargs)

                def choose_and_save():
                    boxes = [w for w in descendants(root)
                             if isinstance(w, ttk.Combobox)]
                    rate = next((b for b in boxes
                                 if "Rápida (≈1,3×)" in b.cget("values")), None)
                    voice = next((b for b in boxes
                                  if chosen_voice in b.cget("values")), None)
                    if rate is None or voice is None:
                        root.after(100, choose_and_save)
                        return
                    rate.set("Rápida (≈1,3×)")
                    voice.set(chosen_voice)
                    toggle = next(b for b in boxes
                                  if "ScrollLock" in b.cget("values"))
                    read = next(b for b in boxes
                                if "Desativado" in b.cget("values"))
                    toggle.set("Ctrl+Alt+K")
                    read.set("Ctrl+Shift+F12")
                    save = next(w for w in descendants(root)
                                if isinstance(w, ttk.Button)
                                and w.cget("text") == "Salvar")
                    save.invoke()
                    windows.append(root.winfo_exists())

                root.after(300, choose_and_save)
                return root

            tk.Tk = settings_root
            show_settings_window(
                dict(DEFAULT_CONFIG), saved.append,
                model_options=MODEL_OPTIONS,
                actions={"list_voices": lambda: [
                    {"name": chosen_voice, "culture": "pt-BR"},
                ]},
            )
            for _ in range(100):
                overlay_root.update()
                if saved:
                    break
                time.sleep(0.05)
            print("RESULT=" + json.dumps({
                "rate": saved[0]["speech_rate"] if saved else None,
                "voice": saved[0]["speech_voices"].get("pt") if saved else None,
                "toggle": saved[0]["hotkey_toggle"] if saved else None,
                "read": saved[0]["hotkey_read"] if saved else None,
                "open": windows[0] if windows else None,
            }), flush=True)
            # Tk foi criado em duas threads; encerrar sem destruí-lo em outra.
            os._exit(0 if saved else 2)
        ''')
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True,
            text=True, timeout=12,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = next(
            line for line in result.stdout.splitlines()
            if line.startswith("RESULT=")
        )
        saved = json.loads(marker.removeprefix("RESULT="))
        self.assertEqual(saved["rate"], 2)
        self.assertEqual(saved["toggle"], "ctrl+alt+k")
        self.assertEqual(saved["read"], "ctrl+shift+f12")
        self.assertEqual(saved["open"], 1)
        self.assertEqual(
            saved["voice"],
            "Microsoft Francisca (Natural) - Portuguese (Brazil)",
        )


if __name__ == "__main__":
    unittest.main()
