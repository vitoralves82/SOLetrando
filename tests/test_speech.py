"""Testes da leitura por voz com o Windows simulado.

A API real (UI Automation, area de transferencia e vozes do Windows) nao roda
no Linux nem na verificacao automatica; aqui validamos a logica em volta dela.
"""

import base64
import json
import os
import subprocess
import tempfile
import threading
import types
import unittest
from unittest import mock

import soletrando_speech
from soletrando_speech import (
    NO_VOICE_ERROR, VOICE_FALLBACK_NOTICE, SpeechReader, is_online_voice,
    list_voices, parse_voice_list, selected_text, voices_for_language,
)


CF_UNICODETEXT = 13
CF_BITMAP = 2


class FakeClipboard:
    """Area de transferencia minima: formatos, texto e numero de sequencia."""

    def __init__(self, text=None, formats=None):
        self.text = text
        self.formats = formats if formats is not None else (
            [CF_UNICODETEXT] if text is not None else []
        )
        self.sequence = 1
        self.emptied = False

    def replace_text(self, text):
        self.text = text
        self.formats = [CF_UNICODETEXT]
        self.sequence += 1


def fake_windll(clipboard):
    def sequence():
        return clipboard.sequence

    sequence_function = mock.Mock(side_effect=sequence)

    def empty():
        clipboard.text = None
        clipboard.formats = []
        clipboard.emptied = True
        clipboard.sequence += 1
        return 1

    user32 = types.SimpleNamespace(
        GetClipboardSequenceNumber=sequence_function,
        OpenClipboard=mock.Mock(return_value=1),
        CloseClipboard=mock.Mock(return_value=1),
        EmptyClipboard=mock.Mock(side_effect=empty),
    )
    return types.SimpleNamespace(user32=user32, kernel32=types.SimpleNamespace())


class FakeClock:
    """Relogio que avanca sozinho para o teste nao esperar de verdade."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        self.now += 0.25
        return self.now

    def sleep(self, _seconds):
        pass


def uia_result(text=None):
    if text is None:
        return types.SimpleNamespace(returncode=2, stdout=b"")
    encoded = base64.b64encode(text.encode("utf-8"))
    return types.SimpleNamespace(returncode=0, stdout=encoded)


class SelectedTextTests(unittest.TestCase):
    def test_windows_clipboard_markers_keep_text_fallback_available(self):
        names = {
            49717: "CanIncludeInClipboardHistory",
            49718: "CanUploadToCloudClipboard",
            49719: "HTML Format",
            49720: "Chromium internal source RFH token",
            49721: "Chromium internal source URL",
        }

        def get_name(fmt, buffer, _size):
            buffer.value = names[fmt]
            return len(buffer.value)

        user32 = types.SimpleNamespace(
            GetClipboardFormatNameW=mock.Mock(side_effect=get_name)
        )
        with mock.patch.object(
            soletrando_speech.ctypes, "windll",
            types.SimpleNamespace(user32=user32), create=True,
        ):
            self.assertTrue(soletrando_speech._is_plain_text_clipboard(
                [CF_UNICODETEXT, 49717, 49718]
            ))
            self.assertTrue(soletrando_speech._is_plain_text_clipboard(
                [CF_UNICODETEXT, 49720, 49721]
            ))
            self.assertFalse(soletrando_speech._is_plain_text_clipboard(
                [CF_UNICODETEXT, 49717, 49719]
            ))

    def run_selected_text(self, clipboard, uia, copy_selection=None, restore=True):
        restored = []

        def restore_text(value):
            restored.append(value)
            if restore:
                clipboard.replace_text(value)
            return restore

        patches = [
            mock.patch.object(soletrando_speech.os, "name", "nt"),
            mock.patch.object(
                soletrando_speech.subprocess, "run", return_value=uia
            ),
            mock.patch.object(
                soletrando_speech.ctypes, "windll", fake_windll(clipboard),
                create=True,
            ),
            mock.patch.object(
                soletrando_speech, "_clipboard_formats",
                side_effect=lambda: list(clipboard.formats),
            ),
            mock.patch.object(
                soletrando_speech, "_clipboard_text",
                side_effect=lambda: clipboard.text,
            ),
            mock.patch.object(
                soletrando_speech, "_is_plain_text_clipboard",
                side_effect=lambda formats: all(
                    fmt == CF_UNICODETEXT for fmt in formats
                ),
            ),
            mock.patch.object(soletrando_speech, "time", FakeClock()),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        copy_selection = copy_selection or mock.Mock()
        result = selected_text(
            copy_selection=copy_selection, restore_text=restore_text
        )
        return result, restored, copy_selection

    def test_accessible_selection_does_not_touch_clipboard(self):
        clipboard = FakeClipboard("conteudo do usuario")
        result, restored, copy = self.run_selected_text(
            clipboard, uia_result("Texto acessível com acentuação")
        )
        self.assertEqual(result, "Texto acessível com acentuação")
        copy.assert_not_called()
        self.assertEqual(restored, [])
        self.assertEqual(clipboard.text, "conteudo do usuario")

    def test_copy_fallback_restores_original_text(self):
        clipboard = FakeClipboard("conteudo do usuario")
        result, restored, _copy = self.run_selected_text(
            clipboard, uia_result(None),
            copy_selection=lambda: clipboard.replace_text("trecho selecionado"),
        )
        self.assertEqual(result, "trecho selecionado")
        self.assertEqual(restored, ["conteudo do usuario"])
        self.assertEqual(clipboard.text, "conteudo do usuario")

    def test_non_text_clipboard_is_left_untouched(self):
        clipboard = FakeClipboard(formats=[CF_BITMAP])
        result, restored, copy = self.run_selected_text(
            clipboard, uia_result(None)
        )
        self.assertEqual(result, "")
        copy.assert_not_called()
        self.assertEqual(restored, [])
        self.assertEqual(clipboard.formats, [CF_BITMAP])

    def test_nothing_selected_returns_empty_without_restoring(self):
        clipboard = FakeClipboard("conteudo do usuario")
        result, restored, copy = self.run_selected_text(
            clipboard, uia_result(None)
        )
        self.assertEqual(result, "")
        copy.assert_called_once()
        self.assertEqual(restored, [])
        self.assertEqual(clipboard.text, "conteudo do usuario")

    def test_empty_clipboard_is_emptied_again_after_copy(self):
        clipboard = FakeClipboard()
        result, restored, _copy = self.run_selected_text(
            clipboard, uia_result(None),
            copy_selection=lambda: clipboard.replace_text("trecho"),
        )
        self.assertEqual(result, "trecho")
        self.assertEqual(restored, [])
        self.assertTrue(clipboard.emptied)
        self.assertIsNone(clipboard.text)

    def test_failed_restore_is_reported(self):
        clipboard = FakeClipboard("conteudo do usuario")
        with self.assertRaisesRegex(RuntimeError, "restaurar"):
            self.run_selected_text(
                clipboard, uia_result(None),
                copy_selection=lambda: clipboard.replace_text("trecho"),
                restore=False,
            )

    def test_other_systems_return_empty(self):
        with mock.patch.object(soletrando_speech.os, "name", "posix"):
            self.assertEqual(selected_text(mock.Mock(), mock.Mock()), "")


class FakeProcess:
    def __init__(self, returncode=0, stderr=b"", block=False):
        self._final_code = returncode
        self._stderr = stderr
        self._release = threading.Event()
        if not block:
            self._release.set()
        self.returncode = None
        self.terminated = False
        self.received = None
        self.started = threading.Event()

    def communicate(self, data):
        self.received = data
        self.started.set()
        self._release.wait(5)
        self.returncode = 1 if self.terminated else self._final_code
        return b"", self._stderr

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self._release.set()


class SpeechReaderTests(unittest.TestCase):
    def speak(self, process, text="Olá, mundo", language="pt", rate=0, voice=""):
        done = threading.Event()
        results = []

        def on_done(ok, error):
            results.append((ok, error))
            done.set()

        reader = SpeechReader(on_done=on_done)
        patch = mock.patch.object(
            soletrando_speech.subprocess, "Popen", return_value=process
        )
        patch.start()
        self.addCleanup(patch.stop)
        reader.speak(text, language, rate, voice)
        return reader, done, results

    def test_request_carries_text_language_voice_and_rate(self):
        process = FakeProcess()
        _reader, done, results = self.speak(
            process, "Ação rápida", "pt", 2, "Microsoft Francisca"
        )
        self.assertTrue(done.wait(5))
        self.assertEqual(results, [(True, "")])
        request = json.loads(process.received.decode("utf-8"))
        self.assertEqual(
            request,
            {
                "text": "Ação rápida", "language": "pt", "culture": "pt-BR",
                "voice": "Microsoft Francisca", "rate": 2,
            },
        )

    def test_automatic_voice_sends_empty_name(self):
        process = FakeProcess()
        _reader, done, _results = self.speak(process, language="en")
        self.assertTrue(done.wait(5))
        request = json.loads(process.received.decode("utf-8"))
        self.assertEqual((request["voice"], request["culture"]), ("", "en"))

    def test_missing_chosen_voice_reads_with_notice(self):
        process = FakeProcess(returncode=4)
        _reader, done, results = self.speak(process, voice="Voz removida")
        self.assertTrue(done.wait(5))
        self.assertEqual(results, [(True, VOICE_FALLBACK_NOTICE)])

    def test_missing_voice_is_reported_with_its_own_error(self):
        process = FakeProcess(returncode=3, stderr=b"Nenhuma voz instalada para es")
        _reader, done, results = self.speak(process, language="es")
        self.assertTrue(done.wait(5))
        self.assertEqual(results, [(False, NO_VOICE_ERROR)])

    def test_other_failures_keep_the_error_text(self):
        process = FakeProcess(returncode=1, stderr="Falha genérica".encode("utf-8"))
        _reader, done, results = self.speak(process)
        self.assertTrue(done.wait(5))
        self.assertEqual(results, [(False, "Falha genérica")])

    def test_stop_interrupts_without_reporting_completion(self):
        process = FakeProcess(block=True)
        reader, done, results = self.speak(process)
        self.assertTrue(process.started.wait(5))
        self.assertTrue(reader.is_active())
        self.assertTrue(reader.stop())
        self.assertTrue(process.terminated)
        self.assertFalse(done.wait(0.3))
        self.assertEqual(results, [])
        self.assertFalse(reader.is_active())

    def test_stop_when_idle_reports_nothing_to_stop(self):
        self.assertFalse(SpeechReader().stop())

    def test_speak_script_applies_rate_voice_and_exit_codes(self):
        script = soletrando_speech._SPEAK_SCRIPT
        self.assertIn("$speaker.Rate = $rate", script)
        self.assertIn("$speaker.Voice = $chosen.token", script)
        self.assertIn(f"exit {soletrando_speech.NO_VOICE_EXIT_CODE}", script)
        self.assertIn(
            f"exit {soletrando_speech.VOICE_FALLBACK_EXIT_CODE}", script
        )
        # Texto como "<b>" deve ser lido, nao tratado como marcacao do SAPI.
        self.assertIn("$speaker.Speak([string]$request.text, 16)", script)


def encoded_voices(value):
    return base64.b64encode(json.dumps(value).encode("utf-8"))


VOICES = [
    {"name": "Microsoft Zira Desktop - English (United States)", "culture": "en-US"},
    {"name": "Microsoft Helia - Portuguese (Portugal)", "culture": "pt-PT"},
    {"name": "Microsoft Maria Desktop - Portuguese(Brazil)", "culture": "pt-BR"},
    {"name": "Microsoft Francisca (Natural) - Portuguese (Brazil)", "culture": "pt-BR"},
    {"name": "Microsoft Thalita Online (Natural) - Portuguese (Brazil)", "culture": "pt-BR"},
]


class VoiceListTests(unittest.TestCase):
    def test_parse_keeps_order_and_drops_invalid_or_repeated(self):
        raw = encoded_voices([
            {"name": "Voz A", "culture": "pt-BR"},
            {"name": "  ", "culture": "pt-BR"},
            "texto solto",
            {"name": "Voz A", "culture": "pt-BR"},
            {"name": "Voz B"},
        ])
        self.assertEqual(
            parse_voice_list(raw),
            [
                {"name": "Voz A", "culture": "pt-BR"},
                {"name": "Voz B", "culture": ""},
            ],
        )

    def test_parse_accepts_single_object_and_rejects_garbage(self):
        self.assertEqual(
            parse_voice_list(encoded_voices({"name": "Única", "culture": "pt-BR"})),
            [{"name": "Única", "culture": "pt-BR"}],
        )
        self.assertEqual(parse_voice_list(b"nao-e-base64!"), [])
        self.assertEqual(parse_voice_list(encoded_voices("texto")), [])

    def test_brazilian_voices_come_first_for_portuguese(self):
        names = [voice["name"] for voice in voices_for_language(VOICES, "pt")]
        self.assertEqual(
            names,
            [
                "Microsoft Maria Desktop - Portuguese(Brazil)",
                "Microsoft Francisca (Natural) - Portuguese (Brazil)",
                "Microsoft Thalita Online (Natural) - Portuguese (Brazil)",
                "Microsoft Helia - Portuguese (Portugal)",
            ],
        )

    def test_other_languages_match_by_prefix(self):
        self.assertEqual(
            [voice["culture"] for voice in voices_for_language(VOICES, "en")],
            ["en-US"],
        )
        self.assertEqual(voices_for_language(VOICES, "es"), [])
        self.assertEqual(voices_for_language(None, "pt"), [])

    def test_online_voices_are_identified_by_name(self):
        self.assertTrue(is_online_voice(VOICES[4]["name"]))
        self.assertFalse(is_online_voice(VOICES[3]["name"]))

    def test_list_voices_reads_the_script_output(self):
        result = types.SimpleNamespace(
            returncode=0, stdout=encoded_voices(VOICES[:1]) + b"\r\n"
        )
        with mock.patch.object(soletrando_speech.os, "name", "nt"), \
                mock.patch.object(
                    soletrando_speech.subprocess, "run", return_value=result
                ):
            self.assertEqual(list_voices(), VOICES[:1])

    def test_list_voices_failures_return_empty(self):
        failed = types.SimpleNamespace(returncode=1, stdout=b"")
        with mock.patch.object(soletrando_speech.os, "name", "nt"):
            with mock.patch.object(
                soletrando_speech.subprocess, "run", return_value=failed
            ):
                self.assertEqual(list_voices(), [])
            with mock.patch.object(
                soletrando_speech.subprocess, "run",
                side_effect=subprocess.TimeoutExpired("powershell", 20),
            ):
                self.assertEqual(list_voices(), [])
        with mock.patch.object(soletrando_speech.os, "name", "posix"):
            self.assertEqual(list_voices(), [])


@unittest.skipUnless(os.name == "nt", "SAPI 5 so existe no Windows")
class WindowsSapiTests(unittest.TestCase):
    """Executa os scripts reais contra o SAPI 5 do Windows da verificacao."""

    def run_script(self, script, request=None):
        return subprocess.run(
            soletrando_speech._powershell(script),
            input=json.dumps(request).encode("utf-8") if request else None,
            capture_output=True, timeout=120,
        )

    def test_list_script_returns_valid_voice_list(self):
        result = self.run_script(soletrando_speech._LIST_VOICES_SCRIPT)
        self.assertEqual(
            result.returncode, 0, result.stderr.decode("utf-8", "replace")
        )
        raw = result.stdout.strip()
        json.loads(base64.b64decode(raw).decode("utf-8"))
        voices = parse_voice_list(raw)
        for voice in voices:
            self.assertTrue(voice["name"])

    def speak_to_file(self, **request):
        with tempfile.TemporaryDirectory() as folder:
            wav = os.path.join(folder, "voz.wav")
            request = dict(
                {"text": "Teste <b> & ação", "rate": 0, "wav": wav}, **request
            )
            result = self.run_script(soletrando_speech._SPEAK_SCRIPT, request)
            size = os.path.getsize(wav) if os.path.exists(wav) else 0
        return result, size

    def test_chosen_voice_speaks_to_file(self):
        voices = list_voices(timeout=120)
        if not voices:
            self.skipTest("Nenhuma voz SAPI 5 nesta maquina")
        voice = voices[0]
        language = (voice["culture"] or "en-US").split("-")[0]
        result, size = self.speak_to_file(
            language=language, culture=voice["culture"], voice=voice["name"]
        )
        self.assertEqual(
            result.returncode, 0, result.stderr.decode("utf-8", "replace")
        )
        self.assertGreater(size, 1000)

    def test_missing_voice_falls_back_or_reports_no_voice(self):
        voices = list_voices(timeout=120)
        if not voices:
            self.skipTest("Nenhuma voz SAPI 5 nesta maquina")
        language = (voices[0]["culture"] or "en-US").split("-")[0]
        result, size = self.speak_to_file(
            language=language, culture=voices[0]["culture"],
            voice="Voz que nao existe",
        )
        self.assertEqual(
            result.returncode, soletrando_speech.VOICE_FALLBACK_EXIT_CODE,
            result.stderr.decode("utf-8", "replace"),
        )
        self.assertGreater(size, 1000)

    def test_language_without_voice_exits_with_no_voice_code(self):
        result, _size = self.speak_to_file(language="xx", culture="xx")
        self.assertEqual(result.returncode, soletrando_speech.NO_VOICE_EXIT_CODE)


if __name__ == "__main__":
    unittest.main()
