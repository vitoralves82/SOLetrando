"""Testes da leitura por voz com o Windows simulado.

A API real (UI Automation, area de transferencia e vozes do Windows) nao roda
no Linux nem na verificacao automatica; aqui validamos a logica em volta dela.
"""

import base64
import json
import threading
import types
import unittest
from unittest import mock

import soletrando_speech
from soletrando_speech import NO_VOICE_ERROR, SpeechReader, selected_text


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
    def speak(self, process, text="Olá, mundo", language="pt", rate=0):
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
        reader.speak(text, language, rate)
        return reader, done, results

    def test_request_carries_text_language_and_rate(self):
        process = FakeProcess()
        _reader, done, results = self.speak(process, "Ação rápida", "pt", 2)
        self.assertTrue(done.wait(5))
        self.assertEqual(results, [(True, "")])
        request = json.loads(process.received.decode("utf-8"))
        self.assertEqual(
            request, {"text": "Ação rápida", "language": "pt", "rate": 2}
        )

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

    def test_speak_script_applies_rate_and_no_voice_exit_code(self):
        self.assertIn("$voice.Rate = $rate", soletrando_speech._SPEAK_SCRIPT)
        self.assertIn(
            f"exit {soletrando_speech.NO_VOICE_EXIT_CODE}",
            soletrando_speech._SPEAK_SCRIPT,
        )


if __name__ == "__main__":
    unittest.main()
