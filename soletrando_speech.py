"""Leitura local de texto com as vozes instaladas no Windows."""

import base64
import ctypes
import json
import os
import subprocess
import threading
import time


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_SELECTION_SCRIPT = r"""
Add-Type -AssemblyName UIAutomationClient
$element = [System.Windows.Automation.AutomationElement]::FocusedElement
if ($null -eq $element) { exit 2 }
$pattern = $null
if (-not $element.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) { exit 2 }
$ranges = $pattern.GetSelection()
$text = ($ranges | ForEach-Object { $_.GetText(-1) }) -join "`n"
if ([string]::IsNullOrWhiteSpace($text)) { exit 2 }
[Console]::Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text)))
"""

_SPEAK_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $available = @($voice.GetInstalledVoices() | Where-Object { $_.Enabled })
    $language = [string]$request.language
    if ([string]::IsNullOrWhiteSpace($language)) { $language = 'pt' }
    $preferred = if ($language -eq 'pt') { 'pt-BR' } else { $language }
    $chosen = $available | Where-Object {
        $_.VoiceInfo.Culture.Name -eq $preferred
    } | Select-Object -First 1
    if ($null -eq $chosen) {
        $chosen = $available | Where-Object {
            $_.VoiceInfo.Culture.Name.StartsWith($language + '-')
        } | Select-Object -First 1
    }
    if ($null -eq $chosen) { throw "Nenhuma voz instalada para $language" }
    $voice.SelectVoice($chosen.VoiceInfo.Name)
    $voice.Speak([string]$request.text)
} finally { $voice.Dispose() }
"""


def _powershell(script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def _clipboard_text():
    """Devolve None quando a area de transferencia nao contem texto Unicode."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
    user32.IsClipboardFormatAvailable.restype = ctypes.c_int
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    if not user32.IsClipboardFormatAvailable(13) or not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(13)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(ctypes.c_void_p(handle))
    finally:
        user32.CloseClipboard()


def _clipboard_formats():
    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.EnumClipboardFormats.argtypes = [ctypes.c_uint]
    user32.EnumClipboardFormats.restype = ctypes.c_uint
    if not user32.OpenClipboard(None):
        return None
    try:
        formats = []
        current = 0
        while True:
            current = user32.EnumClipboardFormats(current)
            if not current:
                break
            formats.append(current)
        return formats
    finally:
        user32.CloseClipboard()


def _is_plain_text_clipboard(formats):
    user32 = ctypes.windll.user32
    user32.GetClipboardFormatNameW.argtypes = [
        ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_int
    ]
    user32.GetClipboardFormatNameW.restype = ctypes.c_int
    for fmt in formats:
        if fmt in {1, 7, 13, 16}:
            continue
        name = ctypes.create_unicode_buffer(128)
        user32.GetClipboardFormatNameW(fmt, name, len(name))
        if name.value not in {"DataObject", "Ole Private Data"}:
            return False
    return True


def selected_text(copy_selection=None, restore_text=None):
    """Consulta a selecao acessivel; Ctrl+C preserva clipboard de texto simples."""
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            _powershell(_SELECTION_SCRIPT), capture_output=True, timeout=5,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0 and result.stdout.strip():
            return base64.b64decode(result.stdout.strip()).decode("utf-8").strip()
    except (OSError, subprocess.SubprocessError, ValueError, UnicodeError):
        pass

    if copy_selection is None or restore_text is None:
        return ""
    formats = _clipboard_formats()
    if formats is None or not _is_plain_text_clipboard(formats):
        return ""
    original = _clipboard_text() if formats else None
    if formats and original is None:
        return ""
    user32 = ctypes.windll.user32
    user32.GetClipboardSequenceNumber.restype = ctypes.c_uint
    before = user32.GetClipboardSequenceNumber()
    try:
        copy_selection()
        deadline = time.monotonic() + 1.0
        while user32.GetClipboardSequenceNumber() == before and time.monotonic() < deadline:
            time.sleep(0.03)
        if user32.GetClipboardSequenceNumber() == before:
            return ""
        return (_clipboard_text() or "").strip()
    finally:
        if user32.GetClipboardSequenceNumber() != before:
            if original is None:
                if not user32.OpenClipboard(None):
                    raise RuntimeError("Não foi possível restaurar a área de transferência vazia")
                try:
                    if not user32.EmptyClipboard():
                        raise RuntimeError("Não foi possível esvaziar a área de transferência")
                finally:
                    user32.CloseClipboard()
            elif not restore_text(original):
                raise RuntimeError("Não foi possível restaurar a área de transferência")


class SpeechReader:
    """Uma leitura por vez; parar encerra apenas o processo de voz iniciado."""

    def __init__(self, on_done=None):
        self._lock = threading.Lock()
        self._process = None
        self._generation = 0
        self._on_done = on_done

    def speak(self, text, language="pt"):
        self.stop()
        with self._lock:
            self._generation += 1
            generation = self._generation
        threading.Thread(
            target=self._run, args=(text, language, generation), daemon=True,
            name="soletrando-leitura",
        ).start()

    def _run(self, text, language, generation):
        try:
            process = subprocess.Popen(
                _powershell(_SPEAK_SCRIPT), stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=_NO_WINDOW,
            )
            with self._lock:
                if generation != self._generation:
                    process.terminate()
                    return
                self._process = process
            request = json.dumps({"text": text, "language": language}, ensure_ascii=False)
            _output, error = process.communicate(request.encode("utf-8"))
            with self._lock:
                current = generation == self._generation
            if current and self._on_done:
                if process.returncode:
                    self._on_done(False, error.decode("utf-8", errors="replace").strip())
                else:
                    self._on_done(True, "")
        except (OSError, subprocess.SubprocessError) as exc:
            if generation == self._generation and self._on_done:
                self._on_done(False, str(exc))
        finally:
            with self._lock:
                if generation == self._generation:
                    self._process = None

    def stop(self):
        with self._lock:
            self._generation += 1
            process = self._process
            self._process = None
        if process and process.poll() is None:
            process.terminate()
