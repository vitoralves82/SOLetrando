"""Leitura local de texto com as vozes SAPI 5 instaladas no Windows."""

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

# Codigos de saida do processo de voz: sem voz no idioma pedido; e leitura
# feita com a voz automatica porque a voz escolhida nao esta mais instalada.
NO_VOICE_EXIT_CODE = 3
NO_VOICE_ERROR = "sem_voz_no_idioma"
VOICE_FALLBACK_EXIT_CODE = 4
VOICE_FALLBACK_NOTICE = "voz_escolhida_ausente"

# Idioma curto da configuracao -> cultura preferida entre as vozes.
PREFERRED_CULTURES = {"pt": "pt-BR"}

# Listagem e leitura usam o mesmo caminho, o SAPI 5 via COM, para que toda voz
# listada possa ser usada. O SAPI enumera a categoria de vozes inteira,
# inclusive mecanismos que publicam vozes por enumerador (TokenEnums), como os
# adaptadores de vozes naturais do Narrador.
_SAPI_VOICES = r"""
function Get-SapiVoices($speaker) {
    $tokens = $speaker.GetVoices()
    for ($i = 0; $i -lt $tokens.Count; $i++) {
        $token = $tokens.Item($i)
        $culture = ''
        try {
            $ids = ([string]$token.GetAttribute('Language')).Split(';')
            $lcid = [Convert]::ToInt32($ids[0].Trim(), 16)
            $culture = [System.Globalization.CultureInfo]::GetCultureInfo($lcid).Name
        } catch { }
        [pscustomobject]@{
            name = [string]$token.GetDescription()
            culture = $culture
            token = $token
        }
    }
}
"""

_LIST_VOICES_SCRIPT = _SAPI_VOICES + r"""
$speaker = New-Object -ComObject SAPI.SpVoice
$items = @(Get-SapiVoices $speaker | ForEach-Object {
    [pscustomobject]@{ name = $_.name; culture = $_.culture }
})
$json = ConvertTo-Json -InputObject $items -Compress
[Console]::Write([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json)))
"""

_SPEAK_SCRIPT = _SAPI_VOICES + r"""
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
$request = [Console]::In.ReadToEnd() | ConvertFrom-Json
$speaker = New-Object -ComObject SAPI.SpVoice
$available = @(Get-SapiVoices $speaker)
$language = [string]$request.language
if ([string]::IsNullOrWhiteSpace($language)) { $language = 'pt' }
$preferred = [string]$request.culture
if ([string]::IsNullOrWhiteSpace($preferred)) { $preferred = $language }
$wanted = [string]$request.voice
$fallback = $false
$chosen = $null
if (-not [string]::IsNullOrWhiteSpace($wanted)) {
    $chosen = $available | Where-Object { $_.name -eq $wanted } | Select-Object -First 1
    if ($null -eq $chosen) { $fallback = $true }
}
if ($null -eq $chosen) {
    $chosen = $available | Where-Object { $_.culture -eq $preferred } | Select-Object -First 1
}
if ($null -eq $chosen) {
    $chosen = $available | Where-Object { $_.culture -like ($language + '-*') } | Select-Object -First 1
}
if ($null -eq $chosen) {
    [Console]::Error.Write("Nenhuma voz instalada para $language")
    exit 3
}
$speaker.Voice = $chosen.token
$rate = [int]$request.rate
if ($rate -lt -10) { $rate = -10 } elseif ($rate -gt 10) { $rate = 10 }
$speaker.Rate = $rate
$stream = $null
if (-not [string]::IsNullOrWhiteSpace([string]$request.wav)) {
    # Grava em arquivo em vez de tocar; 3 = criar para escrita.
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Open([string]$request.wav, 3, $false)
    $speaker.AudioOutputStream = $stream
}
try {
    # 16 = texto simples: sinais como < e & sao lidos, nao interpretados.
    $null = $speaker.Speak([string]$request.text, 16)
} finally {
    if ($null -ne $stream) { $stream.Close() }
}
if ($fallback) { exit 4 }
"""


def _powershell(script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def preferred_culture(language):
    language = (language or "pt").strip() or "pt"
    return PREFERRED_CULTURES.get(language, language)


def parse_voice_list(raw):
    """Converte a saida do script de listagem em [{"name", "culture"}]."""
    try:
        data = json.loads(base64.b64decode(raw).decode("utf-8"))
    except (ValueError, UnicodeError):
        return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    voices, seen = [], set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        voices.append({"name": name, "culture": str(item.get("culture") or "")})
    return voices


def list_voices(timeout=20):
    """Vozes SAPI 5 instaladas, na ordem do Windows. [] fora do Windows ou em falha.

    Pode levar alguns segundos quando um mecanismo de voz consulta vozes
    online; chame fora da thread da interface.
    """
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            _powershell(_LIST_VOICES_SCRIPT), capture_output=True,
            timeout=timeout, creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []
    return parse_voice_list(result.stdout.strip())


def voices_for_language(voices, language):
    """Vozes do idioma, com a cultura preferida (pt-BR para pt) primeiro.

    Segue a mesma ordem que a leitura usa na escolha automatica, entao a
    primeira da lista e a voz que o modo automatico vai usar.
    """
    language = (language or "pt").strip().lower() or "pt"
    preferred = preferred_culture(language).lower()
    first, others = [], []
    for voice in voices or []:
        culture = str(voice.get("culture") or "").lower()
        if culture == preferred:
            first.append(voice)
        elif culture == language or culture.startswith(language + "-"):
            others.append(voice)
    return first + others


def is_online_voice(name):
    """Vozes com "Online" no nome dependem de internet para falar."""
    return "online" in str(name or "").lower()


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
        self._pending = False
        self._on_done = on_done

    def set_on_done(self, callback):
        """callback(ok, erro); erro e NO_VOICE_ERROR quando falta voz.

        Com ok=True, erro pode ser VOICE_FALLBACK_NOTICE: o texto foi lido, mas
        com a voz automatica, porque a voz escolhida nao foi encontrada.
        """
        self._on_done = callback

    def is_active(self):
        """True enquanto uma leitura esta sendo preparada ou falada."""
        with self._lock:
            if self._pending:
                return True
            process = self._process
        return bool(process and process.poll() is None)

    def speak(self, text, language="pt", rate=0, voice=""):
        """voice e o nome exibido pelo Windows; "" usa a primeira voz do idioma."""
        self.stop()
        with self._lock:
            self._generation += 1
            generation = self._generation
            self._pending = True
        threading.Thread(
            target=self._run, args=(text, language, rate, voice, generation),
            daemon=True, name="soletrando-leitura",
        ).start()

    def _run(self, text, language, rate, voice, generation):
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
                self._pending = False
            request = json.dumps(
                {
                    "text": text, "language": language,
                    "culture": preferred_culture(language),
                    "voice": voice or "", "rate": int(rate),
                },
                ensure_ascii=False,
            )
            _output, error = process.communicate(request.encode("utf-8"))
            with self._lock:
                current = generation == self._generation
            if current and self._on_done:
                if process.returncode == NO_VOICE_EXIT_CODE:
                    self._on_done(False, NO_VOICE_ERROR)
                elif process.returncode == VOICE_FALLBACK_EXIT_CODE:
                    self._on_done(True, VOICE_FALLBACK_NOTICE)
                elif process.returncode:
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
                    self._pending = False

    def stop(self):
        """Interrompe a leitura atual. Devolve True se havia algo em andamento."""
        with self._lock:
            was_active = self._pending
            self._generation += 1
            process = self._process
            self._process = None
            self._pending = False
        if process and process.poll() is None:
            process.terminate()
            return True
        return was_active
