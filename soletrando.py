"""
SOLetrando - Ditado por voz local
faster-whisper + CUDA/CPU | Alternativa ao Wispr Flow

Atalhos configuraveis via icone na bandeja do sistema.
Configuracoes salvas em soletrando_config.json.
"""

import argparse
import ctypes
import sys
import time
import warnings
import threading
import queue
import os
import json
import tempfile
import atexit
import re
import unicodedata
from pathlib import Path
from datetime import datetime

IS_WINDOWS = os.name == "nt"

# =====================================================================
# SPLASH SCREEN (fecha automaticamente ao carregar o modelo)
# =====================================================================
# Existe apenas UM root Tk no processo inteiro. A janela de download do
# modelo e criada como Toplevel deste root — dois `tk.Tk()` simultaneos
# nao sao suportados pelo Tkinter e causavam travamentos aleatorios.
_splash = None

def show_splash():
    global _splash
    try:
        import tkinter as tk
        from PIL import Image, ImageTk

        _splash = tk.Tk()
        _splash.overrideredirect(True)
        _splash.attributes("-topmost", True)
        w, h = 320, 200
        x = (_splash.winfo_screenwidth() - w) // 2
        y = (_splash.winfo_screenheight() - h) // 2
        _splash.geometry(f"{w}x{h}+{x}+{y}")
        _splash.configure(bg="#1a1a2e")

        # Icone
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent
        icon_path = base / "icon_idle.png"
        if icon_path.exists():
            icon_img = Image.open(icon_path).resize((64, 64), Image.LANCZOS)
            icon_photo = ImageTk.PhotoImage(icon_img)
            icon_label = tk.Label(_splash, image=icon_photo, bg="#1a1a2e")
            icon_label.image = icon_photo
            icon_label.pack(pady=(20, 5))

        # Nome
        tk.Label(
            _splash, text="SOLetrando",
            font=("Segoe UI", 18), fg="white", bg="#1a1a2e",
        ).pack(pady=(5, 2))

        # Status
        tk.Label(
            _splash, text="Carregando modelo...",
            font=("Segoe UI", 12), fg="#aaaaaa", bg="#1a1a2e",
        ).pack(pady=(2, 10))

        _splash.update()
    except Exception:
        _splash = None

def close_splash():
    global _splash
    if _splash is not None:
        try:
            _splash.destroy()
        except Exception:
            pass
        _splash = None

show_splash()

warnings.filterwarnings("ignore")

# =====================================================================
# PATHS
# =====================================================================
# Pasta de instalacao (onde esta o .exe)
if getattr(sys, "frozen", False):
    INSTALL_DIR = Path(sys.executable).parent
else:
    INSTALL_DIR = Path(__file__).parent

# Pasta de dados do usuario
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", INSTALL_DIR)) / "Soletrando"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache de modelos dentro da pasta de dados: assim o desinstalador
# (que apaga %LOCALAPPDATA%\Soletrando) tambem remove os GB de modelos.
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = DATA_DIR / "soletrando.log"
CONFIG_PATH = DATA_DIR / "soletrando_config.json"
HAS_CONSOLE = sys.stdout is not None and hasattr(sys.stdout, "write")

LOG_MAX_BYTES = 1024 * 1024  # 1 MB antes de rotacionar
_log_lock = threading.Lock()


def _rotate_log_if_needed():
    """Mantem no maximo 2 arquivos de log (atual + .1)."""
    try:
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_MAX_BYTES:
            backup = LOG_PATH.with_suffix(".log.1")
            backup.unlink(missing_ok=True)
            LOG_PATH.rename(backup)
    except Exception:
        pass


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    with _log_lock:
        _rotate_log_if_needed()
        try:
            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        if HAS_CONSOLE:
            try:
                print(line)
            except Exception:
                pass


def show_error_box(msg, title="SOLetrando - Erro"):
    """Mostra erro em MessageBox — sem isso, no .exe sem console o app
    morria silenciosamente e o usuario nao tinha nenhum retorno."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, str(msg), title, 0x10 | 0x40000)
    except Exception:
        pass


def fatal(msg):
    log(f"ERRO FATAL: {msg}")
    close_splash()
    show_error_box(msg)
    sys.exit(1)


# =====================================================================
# CONFIG (hotkeys + modelo)
# =====================================================================
DEFAULT_CONFIG = {
    "hotkey_toggle": "scroll lock",
    "hotkey_quit": "ctrl+shift+q",
    # large-v3-turbo: 809M params (praticamente o tamanho do medium) com
    # precisao de classe "large" e varias vezes mais rapido. Torna o medium
    # obsoleto em qualidade e velocidade.
    "model": "large-v3-turbo",
    "language": "pt",
    "beep_enabled": False,
    # "paste" = Ctrl+V (instantaneo, unicode perfeito)
    # "type"  = simula digitacao tecla a tecla (compativel com terminais)
    "insert_mode": "paste",
}

# Opcoes de hotkey disponiveis no menu
HOTKEY_OPTIONS = [
    ("ScrollLock", "scroll lock"),
    ("F8", "f8"),
    ("F9", "f9"),
    ("F10", "f10"),
    ("Pause", "pause"),
    ("Ctrl+Shift+F", "ctrl+shift+f"),
    ("Ctrl+Shift+R", "ctrl+shift+r"),
    ("Ctrl+Alt+Space", "ctrl+alt+space"),
]

MODEL_OPTIONS = [
    ("tiny (mais rapido)", "tiny"),
    ("base", "base"),
    ("small", "small"),
    ("medium", "medium"),
    ("large-v3-turbo (recomendado)", "large-v3-turbo"),
    ("large-v3 (maxima precisao)", "large-v3"),
]

LANGUAGE_OPTIONS = [
    ("Portugues", "pt"),
    ("Ingles", "en"),
    ("Espanhol", "es"),
    ("Deteccao automatica", ""),
]

QUIT_KEY_OPTIONS = [
    ("Ctrl+Shift+Q", "ctrl+shift+q"),
    ("Ctrl+Alt+Q", "ctrl+alt+q"),
    ("Ctrl+Shift+E", "ctrl+shift+e"),
]

INSERT_MODE_OPTIONS = [
    ("Colar (rapido)", "paste"),
    ("Digitar (compativel)", "type"),
]

VALID_HOTKEY_TOGGLE_KEYS = {key for _, key in HOTKEY_OPTIONS}
VALID_HOTKEY_QUIT_KEYS = {key for _, key in QUIT_KEY_OPTIONS}
VALID_MODEL_KEYS = {key for _, key in MODEL_OPTIONS}
VALID_INSERT_MODES = {key for _, key in INSERT_MODE_OPTIONS}


def is_valid_language(value):
    """Aceita "" (automatico) ou um codigo tipo pt, en, pt-br."""
    if value == "":
        return True
    return bool(re.fullmatch(r"[a-z]{2,3}(-[a-z]{2,4})?", str(value).lower()))


def sanitize_config(cfg):
    """Normaliza configuracao para evitar valores invalidos/corrompidos."""
    normalized = dict(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        normalized.update(cfg)

    if normalized["hotkey_toggle"] not in VALID_HOTKEY_TOGGLE_KEYS:
        normalized["hotkey_toggle"] = DEFAULT_CONFIG["hotkey_toggle"]
    if normalized["hotkey_quit"] not in VALID_HOTKEY_QUIT_KEYS:
        normalized["hotkey_quit"] = DEFAULT_CONFIG["hotkey_quit"]
    if normalized["model"] not in VALID_MODEL_KEYS:
        normalized["model"] = DEFAULT_CONFIG["model"]
    if not is_valid_language(normalized.get("language")):
        normalized["language"] = DEFAULT_CONFIG["language"]
    if not isinstance(normalized.get("beep_enabled"), bool):
        normalized["beep_enabled"] = DEFAULT_CONFIG["beep_enabled"]
    if normalized.get("insert_mode") not in VALID_INSERT_MODES:
        normalized["insert_mode"] = DEFAULT_CONFIG["insert_mode"]
    return normalized


def load_config():
    try:
        if CONFIG_PATH.exists():
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            return sanitize_config(cfg)
    except Exception as e:
        log(f"Erro ao carregar config: {e}")
    return sanitize_config(DEFAULT_CONFIG)


def save_config(cfg):
    """Grava de forma atomica: um crash no meio da escrita deixava o JSON
    truncado e a config do usuario era perdida no proximo boot."""
    try:
        tmp_path = CONFIG_PATH.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)
        log(f"Config salva: {cfg}")
    except Exception as e:
        log(f"Erro ao salvar config: {e}")


config = load_config()

# =====================================================================
# ARGUMENTOS (override da config)
# =====================================================================
parser = argparse.ArgumentParser(description="SOLetrando - Ditado por voz local")
parser.add_argument("--model", default=None,
                    help="Modelo Whisper: tiny, base, small, medium, large-v3-turbo (padrao), large-v3")
parser.add_argument("--language", default=None,
                    help="Idioma: pt (padrao), en, es, fr, de... ou 'auto' para deteccao automatica")
# parse_known_args: argumentos extras (ex.: passados pelo atalho do Windows)
# nao derrubam mais o app com um erro de argparse invisivel no modo .exe.
args, _unknown_args = parser.parse_known_args()

if args.model:
    if args.model in VALID_MODEL_KEYS:
        config["model"] = args.model
    else:
        log(f"Modelo invalido via argumento ({args.model}), usando '{config['model']}'")
if args.language is not None:
    lang = "" if args.language.lower() in ("auto", "") else args.language.lower()
    if is_valid_language(lang):
        config["language"] = lang
    else:
        log(f"Idioma invalido via argumento ({args.language}), usando '{config['language']}'")

log(f"Iniciando SOLetrando - modelo={config['model']}, idioma={config['language'] or 'auto'}")


# =====================================================================
# SINGLE INSTANCE
# =====================================================================
# Feito ANTES dos imports pesados: uma segunda execucao encerra em
# milissegundos em vez de carregar numpy/faster-whisper antes de desistir.
#
# No Windows usamos um mutex nomeado. A versao anterior usava
# os.kill(pid, 0), que no Windows NAO checa existencia de processo —
# sinal 0 e CTRL_C_EVENT, entao a chamada falhava para um processo sem
# console, a excecao era engolida, e a segunda instancia subia junto com a
# primeira. Duas instancias disputando o mesmo atalho global.
MUTEX_NAME = "Local\\SOLetrando_SingleInstance_v1"
LOCK_FILE = Path(tempfile.gettempdir()) / "soletrando.lock"
_mutex_handle = None


def ensure_single_instance():
    """Retorna True se esta e a unica instancia."""
    global _mutex_handle

    if IS_WINDOWS:
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
            ERROR_ALREADY_EXISTS = 183
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                return False
            return True
        except Exception as e:
            log(f"Falha no mutex de instancia unica: {e}")
            return True

    # POSIX (desenvolvimento): aqui os.kill(pid, 0) realmente e uma checagem.
    try:
        if LOCK_FILE.exists():
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            try:
                os.kill(old_pid, 0)
                return False
            except OSError:
                pass
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        log(f"Falha no lock de instancia unica: {e}")
    return True


def cleanup_lock():
    if IS_WINDOWS:
        return
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


atexit.register(cleanup_lock)

if not ensure_single_instance():
    log("Ja existe uma instancia do SOLetrando rodando. Encerrando esta.")
    close_splash()
    sys.exit(0)


# =====================================================================
# IMPORTS PESADOS
# =====================================================================
try:
    import numpy as np
    from faster_whisper import WhisperModel
    import sounddevice as sd
    import keyboard
    from PIL import Image, ImageDraw, ImageFont
    import pystray
except Exception as e:  # dependencia faltando / DLL quebrada no .exe
    fatal(f"Falha ao carregar dependencias:\n\n{e}")

try:
    from faster_whisper.utils import _MODELS as FW_MODELS
except Exception:
    FW_MODELS = {}

# =====================================================================
# DETECCAO DE GPU (sem torch)
# =====================================================================
def _cuda_available():
    if not IS_WINDOWS:
        return False
    try:
        ctypes.CDLL("nvcuda.dll")
        return True
    except OSError:
        return False


# =====================================================================
# DOWNLOAD/CARREGAMENTO DO MODELO COM PROGRESSO
# =====================================================================
# tkinter e opcional: sem ele o app perde apenas o splash/barra de
# progresso, em vez de nao abrir (algumas instalacoes de Python nao trazem
# o tkinter, e o import solto aqui derrubava o processo inteiro).
try:
    import tkinter as tk
    from tkinter import ttk
except Exception:
    tk = None
    ttk = None

from huggingface_hub import scan_cache_dir


def _repo_id_for(model_name):
    """faster-whisper nao usa 'Systran/faster-whisper-<nome>' para todos os
    modelos (turbo vem de outro repo). Hardcodar o prefixo fazia a checagem
    de cache dar falso-negativo para large-v3-turbo."""
    return FW_MODELS.get(model_name, f"Systran/faster-whisper-{model_name}")


def _cache_contains(model_name, cache_dir=None):
    try:
        if cache_dir is not None and not Path(cache_dir).exists():
            return False
        info = scan_cache_dir(cache_dir) if cache_dir else scan_cache_dir()
        return any(repo.repo_id == _repo_id_for(model_name) for repo in info.repos)
    except Exception:
        return False


def resolve_model_cache(model_name):
    """Devolve (download_root, ja_esta_em_cache).

    Modelos novos vao para MODELS_DIR (limpo na desinstalacao), mas se o
    modelo ja existir no cache padrao do HuggingFace reaproveitamos ele em
    vez de forcar um download de varios GB de novo.
    """
    if _cache_contains(model_name, str(MODELS_DIR)):
        return str(MODELS_DIR), True
    if _cache_contains(model_name):
        return None, True
    return str(MODELS_DIR), False


def build_model(model_name, on_status=None):
    """Cria o WhisperModel com fallback de device/compute_type.

    Ter nvcuda.dll nao garante que o cuDNN esteja instalado; sem o fallback,
    o app simplesmente morria na inicializacao sem mensagem nenhuma.
    """
    download_root, _cached = resolve_model_cache(model_name)
    cpu_threads = min(8, os.cpu_count() or 4)

    attempts = []
    if _cuda_available():
        attempts.append(("cuda", "float16"))
        attempts.append(("cuda", "int8_float16"))
    attempts.append(("cpu", "int8"))

    last_error = None
    for device, compute_type in attempts:
        try:
            if on_status:
                on_status(f"Carregando '{model_name}' em {device.upper()} ({compute_type})...")
            log(f"Carregando faster-whisper '{model_name}' em {device} ({compute_type})...")
            m = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=download_root,
                cpu_threads=cpu_threads if device == "cpu" else 0,
            )
            log(f"Modelo carregado: {model_name} / {device} / {compute_type}")
            return m, device, compute_type
        except Exception as e:
            last_error = e
            log(f"Falha ao carregar em {device}/{compute_type}: {e}")

    raise RuntimeError(f"Nao foi possivel carregar o modelo '{model_name}': {last_error}")


def load_model_with_progress(model_name):
    """Carrega modelo, mostrando janela de progresso se precisar baixar."""
    _root, cached = resolve_model_cache(model_name)
    if cached:
        log(f"Modelo '{model_name}' encontrado em cache")
        return build_model(model_name)

    log(f"Modelo '{model_name}' nao encontrado, iniciando download...")

    if tk is None:
        return build_model(model_name)

    result = {"value": None, "error": None}

    def worker():
        try:
            result["value"] = build_model(model_name)
        except Exception as e:
            result["error"] = e

    # Reaproveita o root do splash (dois tk.Tk() no mesmo processo e uma
    # configuracao nao suportada e instavel).
    owns_root = _splash is None
    root = tk.Tk() if owns_root else _splash

    win = tk.Toplevel(root)
    win.title("SOLetrando")
    win.geometry("420x150")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.protocol("WM_DELETE_WINDOW", lambda: None)  # Impedir fechar

    frame = tk.Frame(win, padx=20, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text=f"Baixando modelo '{model_name}'...\nIsso acontece apenas na primeira vez.",
        justify="center", font=("Segoe UI", 10),
    ).pack(pady=(0, 15))

    progress = ttk.Progressbar(frame, mode="indeterminate", length=350)
    progress.pack()
    progress.start(15)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def check_thread():
        if thread.is_alive():
            root.after(200, check_thread)
        else:
            try:
                win.destroy()
            except Exception:
                pass
            root.quit()

    root.after(200, check_thread)
    root.mainloop()

    if owns_root:
        try:
            root.destroy()
        except Exception:
            pass

    if result["error"]:
        raise result["error"]
    return result["value"]


try:
    model, device, compute_type = load_model_with_progress(config["model"])
except Exception as e:
    fatal(
        f"Nao foi possivel carregar o modelo '{config['model']}'.\n\n{e}\n\n"
        f"Verifique sua conexao com a internet e o espaco em disco.\n"
        f"Detalhes em: {LOG_PATH}"
    )

model_lock = threading.Lock()  # protege 'model' durante troca em tempo real

# =====================================================================
# ESTADO GLOBAL
# =====================================================================
SAMPLE_RATE = 16000
MIN_DURATION_SECONDS = 0.5
# Limite de seguranca: para automaticamente uma gravacao esquecida,
# evitando consumo ilimitado de memoria e estado travado.
MAX_RECORDING_SECONDS = 300

is_recording = False
is_transcribing = False
is_loading_model = False
audio_frames = []
stream = None
state_lock = threading.RLock()
last_toggle_time = 0.0
DEBOUNCE_SECONDS = 0.35
tray_icon = None
current_hotkey_toggle = None
current_hotkey_quit = None
recording_session = 0      # identifica cada gravacao (usado pelo watchdog)
watchdog_timer = None      # cancelado ao parar (antes vazava 1 thread/gravacao)


# =====================================================================
# TRAY ICON
# =====================================================================
COLOR_IDLE = "#FFC107"        # amarelo, igual ao icon_idle.png
COLOR_REC = "#00C853"         # verde, igual ao icon_recording.png
COLOR_TRANSCRIBING = "#FF0000"  # vermelho, igual ao icon_transcribing.png

# Tempo minimo que um estado fica visivel na bandeja. Com o turbo + colagem
# por Ctrl+V a transcricao ficou tao rapida que o icone vermelho piscava por
# poucos milissegundos e passava despercebido.
MIN_STATE_VISIBLE_SECONDS = 0.6


def make_icon_image(color, letter="S"):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2
    ty = (size - th) // 2 - 2
    draw.text((tx, ty), letter, fill="white", font=font)
    return img


ICON_FILES = {
    "idle": "icon_idle.png",
    "recording": "icon_recording.png",
    "transcribing": "icon_transcribing.png",
}


def _icon_search_dirs():
    """Pastas onde procurar os PNGs, em ordem de prioridade.

    sys._MEIPASS cobre o build onefile do PyInstaller, onde os arquivos de
    dados sao extraidos para uma pasta temporaria em vez de ficarem ao lado
    do .exe — nesse modo a busca so em INSTALL_DIR falha e o app caia no
    icone generico desenhado em codigo.
    """
    dirs = [INSTALL_DIR]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(Path(meipass))
    try:
        dirs.append(Path(__file__).parent)
    except NameError:
        pass
    seen = []
    for d in dirs:
        if d not in seen:
            seen.append(d)
    return seen


_icon_cache = {}


def load_icon(state):
    """Carrega o PNG do estado; fallback para icone colorido gerado em codigo."""
    if state in _icon_cache:
        return _icon_cache[state]

    filename = ICON_FILES.get(state, ICON_FILES["idle"])
    img = None
    for base in _icon_search_dirs():
        try:
            icon_path = base / filename
            if icon_path.exists():
                img = Image.open(icon_path).resize((64, 64), Image.LANCZOS)
                break
        except Exception as e:
            log(f"Erro ao carregar icone {state} em {base}: {e}")

    if img is None:
        # Fallback com as MESMAS cores dos PNGs (amarelo/verde/vermelho), para
        # que o feedback visual continue correto mesmo sem os arquivos.
        log(f"Icone '{filename}' nao encontrado, usando icone gerado para '{state}'")
        colors = {"idle": COLOR_IDLE, "recording": COLOR_REC, "transcribing": COLOR_TRANSCRIBING}
        return make_icon_image(colors.get(state, COLOR_IDLE), "S")

    # So o PNG e cacheado: uma falha temporaria de leitura nao fica presa
    # para sempre no cache.
    _icon_cache[state] = img
    return img


def idle_title():
    lang = config["language"] or "auto"
    return f"SOLetrando [{config['model']} | {lang}] - {config['hotkey_toggle'].title()} para gravar"


_tray_state = None


def update_tray(state, extra=None):
    """Troca o icone da bandeja: amarelo=parado, verde=gravando, vermelho=transcrevendo."""
    global _tray_state

    if tray_icon is None:
        return
    try:
        tray_icon.icon = load_icon(state)
        if state == "recording":
            tray_icon.title = "SOLetrando - Gravando..."
        elif state == "transcribing":
            tray_icon.title = extra or "SOLetrando - Transcrevendo... aguarde"
        else:
            tray_icon.title = extra or idle_title()

        # pystray so envia o icone para a bandeja quando 'visible' e True; se
        # por algum motivo ele estiver oculto, reexibimos em vez de deixar o
        # usuario sem nenhum retorno visual.
        if not getattr(tray_icon, "visible", True):
            tray_icon.visible = True

        if state != _tray_state:
            log(f"Icone da bandeja -> {state}")
            _tray_state = state
    except Exception as e:
        log(f"Erro ao atualizar tray ({state}): {e}")


def notify(message, title="SOLetrando"):
    try:
        if tray_icon is not None:
            tray_icon.notify(message, title)
    except Exception:
        pass


# =====================================================================
# HOTKEY MANAGEMENT
# =====================================================================
# POR QUE NAO USAMOS keyboard.add_hotkey NO WINDOWS
# -------------------------------------------------
# A biblioteca `keyboard` instala um WH_KEYBOARD_LL: um hook global de baixo
# nivel. TODA tecla digitada em QUALQUER programa do sistema passa por uma
# funcao Python dentro desse hook (keyboard/_winkeyboard.py: process_key), o
# que exige adquirir o GIL antes de qualquer coisa.
#
# O Windows da a esse hook um orcamento de tempo — o valor de
# HKCU\Control Panel\Desktop\LowLevelHooksTimeout, 300 ms por padrao — e, do
# Windows 7 em diante, REMOVE o hook silenciosamente quando o limite estoura.
# Nao ha excecao, nao ha aviso, nao ha log.
#
# Basta uma transcricao (ou o antivirus inspecionando o processo, ou o disco
# engasgando ao gravar o log) segurar o GIL por mais de 300 ms para o hook
# morrer. O app continua vivo, o icone continua na bandeja, o menu continua
# abrindo — mas o atalho nunca mais responde ate reiniciar o programa. Era
# exatamente o sintoma de "para de funcionar depois de alguns minutos de uso"
# e a razao de parecer que "o Windows esta bloqueando".
#
# RegisterHotKey nao usa hook nenhum: o Windows entrega um WM_HOTKEY direto na
# fila de mensagens da thread que registrou o atalho. Nao ha orcamento de
# tempo para estourar, nao ha hook para ser removido, e o custo por tecla
# digitada no resto do sistema passa a ser zero.
WM_HOTKEY = 0x0312
WM_APP_RELOAD = 0x8001   # WM_APP + 1
WM_APP_STOP = 0x8002     # WM_APP + 2
PM_NOREMOVE = 0x0000

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000    # segurar a tecla nao dispara o atalho repetidas vezes

ERROR_HOTKEY_ALREADY_REGISTERED = 1409

HOTKEY_ID_TOGGLE = 1
HOTKEY_ID_QUIT = 2

_VK_BY_NAME = {
    "scroll lock": 0x91,
    "pause": 0x13,
    "space": 0x20,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "enter": 0x0D,
    "backspace": 0x08,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "page up": 0x21,
    "page down": 0x22,
    "print screen": 0x2C,
}
for _n in range(1, 25):
    _VK_BY_NAME[f"f{_n}"] = 0x6F + _n            # VK_F1 == 0x70
for _ch in "abcdefghijklmnopqrstuvwxyz0123456789":
    _VK_BY_NAME[_ch] = ord(_ch.upper())

_MOD_BY_NAME = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "alt": MOD_ALT,
    "win": MOD_WIN,
    "windows": MOD_WIN,
    "super": MOD_WIN,
}


def parse_hotkey_spec(spec):
    """'ctrl+shift+q' -> (MOD_CONTROL | MOD_SHIFT, VK_Q). None se nao mapeavel."""
    mods = 0
    vk = None
    for part in str(spec).lower().split("+"):
        part = part.strip()
        if not part:
            return None
        if part in _MOD_BY_NAME:
            mods |= _MOD_BY_NAME[part]
        elif vk is None and part in _VK_BY_NAME:
            vk = _VK_BY_NAME[part]
        else:
            return None
    if vk is None:
        return None
    return mods, vk


class _MSG(ctypes.Structure):
    """MSG do Win32. O campo extra no fim e apenas folga defensiva, para o
    caso de o GetMessageW escrever uma struct maior que a declarada aqui."""
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
        ("_reserved", ctypes.c_ulonglong),
    ]


class Win32HotkeyManager:
    """Atalhos globais via RegisterHotKey, em thread propria com message loop.

    RegisterHotKey e por thread: so a thread que registrou recebe o WM_HOTKEY
    e so ela pode registrar/cancelar. Por isso toda troca de atalho e enviada
    para essa thread com PostThreadMessageW, em vez de mexer nos registros de
    fora.

    Os callbacks rodam numa thread de despacho separada, para que abrir o
    microfone (que pode levar centenas de milissegundos) nunca segure o loop
    de mensagens e atrase o proximo atalho.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._apply_lock = threading.Lock()
        self._callbacks = {}        # id -> (rotulo, funcao)
        self._desired = {}          # id -> (spec, mods, vk)
        self._active = {}           # id -> (spec, mods, vk) — so a thread mexe
        self._result = {}
        self._result_event = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self._thread_id = None
        self._jobs = queue.Queue()
        self._worker = None

    # ------------------------------------------------------------------
    # API publica (pode ser chamada de qualquer thread)
    # ------------------------------------------------------------------
    def set_callback(self, hotkey_id, label, callback):
        with self._lock:
            self._callbacks[hotkey_id] = (label, callback)

    def is_alive(self):
        thread = self._thread
        return bool(thread and thread.is_alive() and self._ready.is_set())

    def inactive_specs(self):
        """Atalhos que deveriam estar valendo mas nao estao."""
        with self._lock:
            desired = dict(self._desired)
        if not desired:
            return []
        if not self.is_alive():
            return [entry[0] for entry in desired.values()]
        return [entry[0] for hid, entry in desired.items()
                if self._active.get(hid) != entry]

    def apply(self, specs, timeout=5.0):
        """Aplica {id: 'ctrl+shift+q'}.

        Retorna {id: None | mensagem_de_erro}, ou None se o backend Win32 nao
        estiver disponivel — nesse caso o chamador cai no fallback.
        """
        if not IS_WINDOWS:
            return None

        parsed = {}
        errors = {}
        for hid, spec in specs.items():
            parsed_spec = parse_hotkey_spec(spec)
            if parsed_spec is None:
                errors[hid] = f"o atalho '{spec}' nao e suportado pelo Windows"
            else:
                parsed[hid] = (spec, parsed_spec[0], parsed_spec[1])

        with self._apply_lock:
            with self._lock:
                self._desired = parsed
            self._result_event.clear()
            if not self._ensure_started():
                log("Nao foi possivel iniciar a thread de hotkeys do Windows")
                return None
            if not self._post(WM_APP_RELOAD):
                return None
            if not self._result_event.wait(timeout):
                log("Timeout ao aplicar os atalhos na thread de hotkeys")
                return None
            with self._lock:
                result = dict(self._result)

        result.update(errors)
        return result

    def stop(self):
        self._post(WM_APP_STOP)
        self._jobs.put(None)

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------
    def _ensure_started(self):
        if self.is_alive():
            return True
        thread = self._thread
        if thread is not None and thread.is_alive():
            return self._ready.wait(3.0)  # ainda subindo

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._loop, name="soletrando-hotkeys", daemon=True)
        self._thread.start()

        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(
                target=self._dispatch_loop, name="soletrando-hotkeys-dispatch",
                daemon=True)
            self._worker.start()

        return self._ready.wait(3.0)

    def _post(self, message):
        thread_id = self._thread_id
        if not thread_id:
            return False
        try:
            user32 = ctypes.windll.user32
            user32.PostThreadMessageW.argtypes = [
                ctypes.c_ulong, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
            return bool(user32.PostThreadMessageW(thread_id, message, 0, 0))
        except Exception as e:
            log(f"Falha ao falar com a thread de hotkeys: {e}")
            return False

    def _loop(self):
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.GetMessageW.restype = ctypes.c_int
            user32.GetMessageW.argtypes = [
                ctypes.POINTER(_MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
            user32.RegisterHotKey.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
            user32.UnregisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int]

            msg = _MSG()
            # Forca a criacao da fila de mensagens ANTES de publicar o
            # thread_id: sem isso o PostThreadMessageW disparado logo em
            # seguida seria descartado sem erro nenhum.
            user32.PeekMessageW(ctypes.byref(msg), None, 0x0400, 0x0400, PM_NOREMOVE)
            self._thread_id = kernel32.GetCurrentThreadId()
            self._ready.set()
            log("Thread de hotkeys (RegisterHotKey) iniciada")

            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret in (0, -1):  # WM_QUIT ou erro
                    break
                if msg.message == WM_HOTKEY:
                    self._jobs.put(int(msg.wParam))
                elif msg.message == WM_APP_RELOAD:
                    self._reload(user32, kernel32)
                elif msg.message == WM_APP_STOP:
                    break
        except Exception as e:
            log(f"Thread de hotkeys terminou com erro: {e}")
        finally:
            self._ready.clear()
            self._thread_id = None
            try:
                self._unregister_all()
            except Exception:
                pass
            log("Thread de hotkeys encerrada")

    def _dispatch_loop(self):
        while True:
            hotkey_id = self._jobs.get()
            if hotkey_id is None:
                return
            with self._lock:
                entry = self._callbacks.get(hotkey_id)
            if entry is None:
                continue
            label, callback = entry
            try:
                callback()
            except Exception as e:
                log(f"Erro no callback do atalho '{label}': {e}")

    def _reload(self, user32, kernel32):
        with self._lock:
            desired = dict(self._desired)
        result = {}

        for hid in list(self._active):
            if self._active[hid] != desired.get(hid):
                user32.UnregisterHotKey(None, hid)
                del self._active[hid]

        for hid, entry in desired.items():
            if self._active.get(hid) == entry:
                result[hid] = None
                continue
            spec, mods, vk = entry
            if user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk):
                self._active[hid] = entry
                result[hid] = None
                log(f"Atalho '{spec}' registrado (RegisterHotKey)")
                continue
            # GetLastError e lido imediatamente: qualquer outra chamada Win32
            # no meio sobrescreveria o codigo do erro que interessa.
            err = kernel32.GetLastError()
            if err == ERROR_HOTKEY_ALREADY_REGISTERED:
                result[hid] = (f"o atalho '{spec}' ja esta reservado por outro "
                               f"programa. Escolha outro no menu da bandeja")
            else:
                result[hid] = f"o Windows recusou o atalho '{spec}' (erro {err})"

        with self._lock:
            self._result = result
        self._result_event.set()

    def _unregister_all(self):
        user32 = ctypes.windll.user32
        for hid in list(self._active):
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
            self._active.pop(hid, None)


hotkey_manager = Win32HotkeyManager() if IS_WINDOWS else None
_hotkey_backend = "none"
# O monitor de saude tenta registrar de novo a cada 30s. Sem lembrar o que ja
# foi avisado, um atalho tomado de forma permanente por outro programa viraria
# um balao de notificacao a cada meio minuto.
_notified_hotkey_problems = set()


def register_hotkeys():
    """(Re)registra os atalhos globais. True se todos ficaram ativos."""
    global _hotkey_backend, _notified_hotkey_problems

    if hotkey_manager is not None:
        hotkey_manager.set_callback(HOTKEY_ID_TOGGLE, "gravar", toggle)
        hotkey_manager.set_callback(HOTKEY_ID_QUIT, "encerrar", request_shutdown)
        results = hotkey_manager.apply({
            HOTKEY_ID_TOGGLE: config["hotkey_toggle"],
            HOTKEY_ID_QUIT: config["hotkey_quit"],
        })
        if results is not None:
            _hotkey_backend = "win32"
            problems = {msg for msg in results.values() if msg}
            for msg in sorted(problems):
                log(f"Atalho nao registrado: {msg}.")
                if msg not in _notified_hotkey_problems:
                    notify(f"Atencao: {msg}.")
            _notified_hotkey_problems = problems
            if not problems:
                log(f"Hotkeys ativas via RegisterHotKey: "
                    f"toggle={config['hotkey_toggle']}, quit={config['hotkey_quit']}")
            return not problems
        log("RegisterHotKey indisponivel; caindo para o hook do 'keyboard'")

    return _register_hotkeys_fallback()


def _register_hotkeys_fallback():
    """Caminho antigo, com o hook global do 'keyboard'.

    Usado no Linux (desenvolvimento) e no caso improvavel de o RegisterHotKey
    nao subir no Windows. No Windows este caminho continua sujeito ao
    LowLevelHooksTimeout descrito no topo da secao, entao ele e ultimo recurso.
    """
    global current_hotkey_toggle, current_hotkey_quit, _hotkey_backend

    _hotkey_backend = "keyboard"

    # Remove hotkeys anteriores se existirem
    try:
        if current_hotkey_toggle is not None:
            keyboard.remove_hotkey(current_hotkey_toggle)
    except Exception:
        pass
    try:
        if current_hotkey_quit is not None:
            keyboard.remove_hotkey(current_hotkey_quit)
    except Exception:
        pass
    current_hotkey_toggle = None
    current_hotkey_quit = None

    try:
        current_hotkey_toggle = keyboard.add_hotkey(config["hotkey_toggle"], toggle)
        current_hotkey_quit = keyboard.add_hotkey(config["hotkey_quit"], request_shutdown)
        log(f"Hotkeys registradas (hook do 'keyboard'): "
            f"toggle={config['hotkey_toggle']}, quit={config['hotkey_quit']}")
        return True
    except Exception as e:
        log(f"Erro ao registrar hotkeys: {e}")
        notify(f"Nao foi possivel registrar o atalho {config['hotkey_toggle']}.")
        return False


def change_hotkey_toggle(label, key):
    """Chamado pelo menu do tray para trocar hotkey."""
    def handler(icon, item):
        config["hotkey_toggle"] = key
        save_config(config)
        register_hotkeys()
        update_tray("idle")
        log(f"Hotkey alterada para: {label} ({key})")
    return handler


def change_hotkey_quit(label, key):
    def handler(icon, item):
        config["hotkey_quit"] = key
        save_config(config)
        register_hotkeys()
        log(f"Hotkey encerrar alterada para: {label} ({key})")
    return handler


def _radio_check(config_key, value):
    def check(item):
        return config[config_key] == value
    return check


# =====================================================================
# BEEPS
# =====================================================================
def _beep(freq, duration):
    """winsound.Beep e sincrono; rodar direto no callback do 'keyboard'
    atrasava o inicio da gravacao em ~120ms."""
    def run():
        try:
            import winsound
            winsound.Beep(freq, duration)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def beep_start():
    _beep(800, 120)


def beep_stop():
    _beep(450, 120)


def toggle_beep(icon, item):
    config["beep_enabled"] = not config["beep_enabled"]
    save_config(config)
    log(f"Bip sonoro {'ativado' if config['beep_enabled'] else 'desativado'}")


# =====================================================================
# AUDIO
# =====================================================================
_overflow_logged = False


def audio_callback(indata, frames, time_info, status):
    global _overflow_logged
    if status and not _overflow_logged:
        # Logado uma vez por sessao para nao inundar o arquivo de log.
        log(f"Aviso do stream de audio: {status}")
        _overflow_logged = True
    if is_recording:
        audio_frames.append(indata.copy())


def _close_stream():
    """Para e fecha o stream de audio atual, se existir (sempre seguro)."""
    global stream
    if stream is not None:
        try:
            stream.stop()
        except Exception as e:
            log(f"Erro ao parar stream: {e}")
        try:
            stream.close()
        except Exception as e:
            log(f"Erro ao fechar stream: {e}")
        stream = None


def _cancel_watchdog():
    global watchdog_timer
    if watchdog_timer is not None:
        try:
            watchdog_timer.cancel()
        except Exception:
            pass
        watchdog_timer = None


def _watchdog_stop(session):
    """Auto-para uma gravacao que passou do tempo maximo (por sessao)."""
    with state_lock:
        if not is_recording or session != recording_session:
            return
    log("Gravacao atingiu o tempo maximo, parando automaticamente")
    notify(f"Gravacao parada automaticamente apos {MAX_RECORDING_SECONDS // 60} min.")
    threading.Thread(target=stop_and_transcribe, daemon=True).start()


def start_recording():
    """Deve ser chamado com state_lock adquirido."""
    global is_recording, audio_frames, stream, recording_session, watchdog_timer
    global _overflow_logged

    if is_recording:
        return

    # Fecha qualquer stream residual de uma sessao anterior (evita vazamento)
    _close_stream()
    _cancel_watchdog()

    audio_frames = []
    _overflow_logged = False
    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=audio_callback,
            blocksize=1024,
        )
        stream.start()
    except Exception as e:
        is_recording = False
        _close_stream()
        log(f"Falha ao iniciar gravacao: {e}")
        notify("Nao foi possivel acessar o microfone.\nVerifique o dispositivo de entrada.")
        update_tray("idle")
        return

    recording_session += 1
    session = recording_session
    is_recording = True
    log("REC iniciado")
    update_tray("recording")

    # Watchdog: para automaticamente se a gravacao for esquecida
    watchdog_timer = threading.Timer(MAX_RECORDING_SECONDS, _watchdog_stop, args=(session,))
    watchdog_timer.daemon = True
    watchdog_timer.start()


# =====================================================================
# CLIPBOARD
# =====================================================================
CF_UNICODETEXT = 13
GMEM_MOVEABLE_ZEROINIT = 0x0042


def copy_to_clipboard(text):
    """Copia texto para o clipboard do Windows via ctypes (sem dependencias).

    Correcoes em relacao a versao anterior:
      - restype dos handles setado para c_void_p. Sem isso o ctypes truncava
        HGLOBAL para int de 32 bits em Windows 64-bit e o handle entregue ao
        SetClipboardData era invalido (colagem vinha vazia/lixo).
      - retorno de OpenClipboard checado (o clipboard pode estar tomado por
        outro processo) com algumas tentativas.
      - CloseClipboard garantido no finally; antes, uma excecao no meio
        deixava o clipboard aberto e travava o Ctrl+C/Ctrl+V do sistema todo.
    """
    if not IS_WINDOWS:
        return False

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    opened = False
    for _ in range(10):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)

    if not opened:
        log("Clipboard ocupado por outro processo, nao foi possivel copiar")
        return False

    h_mem = None
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16-le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE_ZEROINIT, len(data))
        if not h_mem:
            log("GlobalAlloc falhou ao copiar para clipboard")
            return False
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            log("GlobalLock falhou ao copiar para clipboard")
            return False
        ctypes.memmove(p_mem, data, len(data))
        kernel32.GlobalUnlock(h_mem)
        if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
            log("SetClipboardData falhou")
            return False
        h_mem = None  # propriedade transferida para o sistema
        log("Texto copiado para clipboard")
        return True
    except Exception as e:
        log(f"Erro ao copiar para clipboard: {e}")
        return False
    finally:
        if h_mem:
            try:
                kernel32.GlobalFree(h_mem)
            except Exception:
                pass
        try:
            user32.CloseClipboard()
        except Exception:
            pass


# =====================================================================
# INSERIR TEXTO
# =====================================================================
MODIFIER_KEYS = ("ctrl", "shift", "alt", "left windows", "right windows")
# VK_SHIFT, VK_CONTROL, VK_MENU (alt), VK_LWIN, VK_RWIN
_MODIFIER_VKS = (0x10, 0x11, 0x12, 0x5B, 0x5C)


def _modifiers_pressed():
    """True se algum modificador esta fisicamente pressionado.

    No Windows usamos GetAsyncKeyState, que le o estado real do teclado. A
    versao anterior usava keyboard.is_pressed(), e essa chamada INSTALA o
    WH_KEYBOARD_LL da biblioteca `keyboard` — ou seja, reintroduziria pela
    porta dos fundos exatamente o hook que o RegisterHotKey veio eliminar.
    """
    if IS_WINDOWS:
        try:
            user32 = ctypes.windll.user32
            user32.GetAsyncKeyState.restype = ctypes.c_short
            user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in _MODIFIER_VKS)
        except Exception:
            return False

    if _hotkey_backend == "keyboard":
        try:
            return any(keyboard.is_pressed(k) for k in MODIFIER_KEYS)
        except Exception:
            return False
    return False


def wait_modifiers_released(timeout=1.5):
    """Espera o usuario soltar Ctrl/Shift/Alt antes de injetar teclas.

    Com hotkeys como Ctrl+Shift+F, o texto era inserido enquanto os
    modificadores ainda estavam pressionados — o Ctrl+V virava Ctrl+Shift+V
    e a digitacao virava atalhos do aplicativo de destino.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _modifiers_pressed():
            return True
        time.sleep(0.02)
    return False


def insert_text(text, clipboard_ok):
    wait_modifiers_released()

    if config["insert_mode"] == "paste" and clipboard_ok:
        try:
            keyboard.send("ctrl+v")
            log("Texto inserido (colar)")
            return True
        except Exception as e:
            log(f"Falha ao colar, tentando digitacao: {e}")

    try:
        # 8ms/caractere deixava um paragrafo levando varios segundos.
        keyboard.write(text, delay=0.003)
        log("Texto inserido (digitacao)")
        return True
    except Exception as e:
        log(f"Falha ao inserir texto: {e}")
        notify("Nao foi possivel inserir o texto. Ele esta no clipboard (Ctrl+V).")
        return False


# =====================================================================
# POS-PROCESSAMENTO
# =====================================================================
# Alucinacoes classicas do Whisper quando o audio e quase silencio.
HALLUCINATION_PHRASES = {
    "legendas pela comunidade amara.org",
    "legendado pela comunidade amara.org",
    "legendas pela comunidade amara org",
    "subtitles by the amara.org community",
    "obrigado por assistir",
    "obrigado por assistir!",
    "inscreva-se no canal",
    "thanks for watching",
    "thank you for watching",
    "thank you.",
    "you",
    ".",
    "...",
}


def _normalize_for_compare(text):
    stripped = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return stripped.strip()


def clean_transcript(text):
    """Normaliza espacos e descarta alucinacoes conhecidas."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    if _normalize_for_compare(text) in HALLUCINATION_PHRASES:
        log(f"Descartado como alucinacao: {text!r}")
        return ""
    return text


# =====================================================================
# TRANSCREVER
# =====================================================================
SILENCE_RMS_THRESHOLD = 0.004   # RMS e mais confiavel que pico isolado
MAX_NORMALIZATION_GAIN = 8.0    # evita amplificar ruido de fundo em 100x


def stop_and_transcribe():
    global is_recording, audio_frames, is_transcribing

    transcribe_started_at = None

    with state_lock:
        if not is_recording or is_transcribing:
            return
        # Flags trocadas dentro do lock: sem isso, o watchdog e o toggle do
        # usuario podiam entrar aqui simultaneamente e transcrever duas vezes.
        is_transcribing = True
        is_recording = False
        _cancel_watchdog()
        _close_stream()
        # Copia local e limpa a lista global (o callback ja nao appenda pois
        # is_recording == False), evitando corrida durante o concatenate.
        frames = audio_frames
        audio_frames = []

    # try/finally garante que is_transcribing SEMPRE volte a False e o tray
    # volte para idle, mesmo diante de uma excecao inesperada. Sem isso, um
    # erro nao previsto deixava a flag presa em True e o app parava de
    # responder a qualquer atalho ate ser reiniciado.
    try:
        if not frames:
            log("Nenhum audio capturado")
            return

        update_tray("transcribing")
        transcribe_started_at = time.monotonic()
        log("Transcrevendo...")

        try:
            audio_data = np.concatenate(frames, axis=0).flatten().astype(np.float32)
        except Exception as e:
            log(f"Erro ao consolidar audio: {e}")
            return
        finally:
            frames = None  # libera a memoria dos blocos originais

        if audio_data.size == 0:
            log("Nenhum audio capturado")
            return

        duration = len(audio_data) / SAMPLE_RATE
        rms = float(np.sqrt(np.mean(np.square(audio_data))))
        peak = float(np.max(np.abs(audio_data)))
        log(f"Audio: {duration:.1f}s (rms={rms:.4f}, pico={peak:.3f})")

        if duration < MIN_DURATION_SECONDS:
            log("Audio muito curto, ignorando")
            return

        # RMS em vez de pico: um estalo do teclado gera pico alto sem fala,
        # e uma fala baixa pode ter pico modesto. RMS separa melhor os dois.
        if rms < SILENCE_RMS_THRESHOLD:
            log("Audio muito silencioso, ignorando")
            return

        # Ganho limitado para nao transformar ruido de fundo em "fala".
        # A versao anterior fazia audio/peak sempre, o que levava um sussurro
        # e o ruido de fundo junto dele ao mesmo nivel de uma fala normal.
        if peak > 0:
            gain = np.float32(min(0.95 / peak, MAX_NORMALIZATION_GAIN))
            if abs(float(gain) - 1.0) > 0.01:
                audio_data = audio_data * gain

        try:
            with model_lock:
                segments, info = model.transcribe(
                    audio_data,
                    language=config["language"] or None,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
                    # Ditado sao trechos curtos e independentes: carregar o
                    # texto anterior como contexto e a principal fonte de
                    # loops e alucinacoes repetidas.
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
            if not config["language"]:
                log(f"Idioma detectado: {info.language} ({info.language_probability:.0%})")
        except Exception as e:
            log(f"Erro na transcricao: {e}")
            notify("Erro na transcricao. Veja o log para detalhes.")
            return

        text = clean_transcript(text)
        if not text:
            log("Nenhuma fala detectada")
            return

        log(f"Texto ({len(text)} chars): {text}")
        clipboard_ok = copy_to_clipboard(text)
        insert_text(text, clipboard_ok)
    except Exception as e:
        log(f"Erro inesperado na transcricao: {e}")
    finally:
        # Segura o icone vermelho pelo tempo minimo antes de voltar ao amarelo.
        # A espera acontece com is_transcribing ainda True, entao um toggle
        # nesse intervalo e ignorado (e registrado) em vez de disputar o estado.
        if transcribe_started_at is not None:
            restante = MIN_STATE_VISIBLE_SECONDS - (time.monotonic() - transcribe_started_at)
            if restante > 0:
                time.sleep(restante)
        with state_lock:
            is_transcribing = False
            # Se o usuario ja comecou outra gravacao, nao sobrescreve o verde.
            if not is_recording:
                update_tray("idle")


# =====================================================================
# TOGGLE
# =====================================================================
def toggle():
    global last_toggle_time

    # Roda na thread do 'keyboard'; um erro nao tratado aqui poderia derrubar
    # o handler silenciosamente. Envolvemos tudo para registrar no log.
    try:
        # monotonic: imune a ajustes de relogio/horario de verao, que com
        # time.time() podiam desabilitar o atalho por horas.
        now = time.monotonic()
        if (now - last_toggle_time) < DEBOUNCE_SECONDS:
            return
        last_toggle_time = now

        with state_lock:
            if is_loading_model:
                log("Toggle ignorado - carregando modelo")
                return
            if is_transcribing:
                log("Toggle ignorado - transcricao em andamento")
                return

            if not is_recording:
                if config["beep_enabled"]:
                    beep_start()
                start_recording()
                return

            if config["beep_enabled"]:
                beep_stop()

        threading.Thread(target=stop_and_transcribe, daemon=True).start()
    except Exception as e:
        log(f"Erro no toggle: {e}")


# =====================================================================
# TROCA DE MODELO EM TEMPO REAL
# =====================================================================
def change_model(model_key):
    global is_loading_model

    if model_key == config["model"]:
        return

    with state_lock:
        if is_recording or is_transcribing or is_loading_model:
            notify("Aguarde a gravacao/transcricao atual terminar.")
            return
        is_loading_model = True

    def worker():
        global model, device, compute_type, is_loading_model
        previous = config["model"]
        try:
            update_tray("transcribing", f"SOLetrando - carregando '{model_key}'...")
            notify(f"Carregando modelo '{model_key}'...")
            new_model, new_device, new_compute = build_model(model_key)
            with model_lock:
                model = new_model
                device = new_device
                compute_type = new_compute
            config["model"] = model_key
            save_config(config)
            log(f"Modelo alterado para '{model_key}' ({new_device}/{new_compute})")
            notify(f"Modelo '{model_key}' pronto.")
        except Exception as e:
            log(f"Falha ao trocar para o modelo '{model_key}': {e}")
            notify(f"Falha ao carregar '{model_key}'. Mantendo '{previous}'.")
        finally:
            with state_lock:
                is_loading_model = False
            update_tray("idle")
            rebuild_menu()

    threading.Thread(target=worker, daemon=True).start()


def change_language(lang_key):
    config["language"] = lang_key
    save_config(config)
    log(f"Idioma alterado para '{lang_key or 'auto'}'")
    update_tray("idle")


def change_insert_mode(mode_key):
    config["insert_mode"] = mode_key
    save_config(config)
    log(f"Modo de insercao alterado para '{mode_key}'")


# =====================================================================
# SHUTDOWN
# =====================================================================
_shutdown_started = threading.Event()


def _do_shutdown():
    global is_recording

    log("Encerrando SOLetrando")

    try:
        if hotkey_manager is not None:
            hotkey_manager.stop()
    except Exception:
        pass
    try:
        if _hotkey_backend == "keyboard":
            keyboard.unhook_all_hotkeys()
    except Exception:
        pass

    with state_lock:
        is_recording = False
        _cancel_watchdog()
        _close_stream()

    cleanup_lock()

    if tray_icon is not None:
        try:
            tray_icon.stop()
        except Exception:
            pass

    # Rede de seguranca: se o loop do pystray nao encerrar (ja aconteceu com
    # o tray "fantasma" preso no Explorer), forca a saida do processo.
    def hard_exit():
        log("Forcando encerramento do processo")
        os._exit(0)

    t = threading.Timer(3.0, hard_exit)
    t.daemon = True
    t.start()


def request_shutdown():
    """Chamado pela hotkey/menu. Roda em thread separada porque
    unhook_all_hotkeys() a partir do proprio callback do 'keyboard' pode
    travar, e sys.exit() fora da main thread nao encerra o processo."""
    if _shutdown_started.is_set():
        return
    _shutdown_started.set()
    threading.Thread(target=_do_shutdown, daemon=True).start()


def on_tray_quit(icon, item):
    request_shutdown()


# =====================================================================
# MONITOR DE SAUDE
# =====================================================================
# Rede de seguranca: mesmo com o RegisterHotKey um atalho pode deixar de
# valer (outro programa registrou a mesma tecla depois de nos, ou a thread
# de mensagens morreu). Sem este monitor o app fica aberto e inerte, que era
# justamente o que o usuario via. Aqui ele se conserta sozinho e, tao
# importante quanto, deixa registrado no log que isso aconteceu.
HEALTH_CHECK_SECONDS = 30
HEARTBEAT_EVERY_CHECKS = 40   # ~20 min entre linhas de "ainda vivo"

_health_thread = None


def _health_loop():
    checks = 0
    while not _shutdown_started.is_set():
        # wait() em vez de sleep(): o encerramento nao espera 30s por isto.
        if _shutdown_started.wait(HEALTH_CHECK_SECONDS):
            return
        checks += 1
        try:
            if _hotkey_backend == "win32" and hotkey_manager is not None:
                inactive = hotkey_manager.inactive_specs()
                if inactive:
                    log(f"Atalhos inativos detectados ({', '.join(inactive)}); "
                        f"tentando registrar de novo")
                    register_hotkeys()
            if checks % HEARTBEAT_EVERY_CHECKS == 0:
                log(f"Heartbeat: atalhos={_hotkey_backend}, gravando={is_recording}, "
                    f"transcrevendo={is_transcribing}")
        except Exception as e:
            log(f"Erro no monitor de saude: {e}")


def start_health_monitor():
    global _health_thread
    if _health_thread is not None and _health_thread.is_alive():
        return
    _health_thread = threading.Thread(
        target=_health_loop, name="soletrando-health", daemon=True)
    _health_thread.start()
    log("Monitor de saude dos atalhos iniciado")


# =====================================================================
# BUILD TRAY MENU
# =====================================================================
def _radio_items(options, config_key, on_change):
    def make_handler(key):
        def handler(icon, item):
            on_change(key)
        return handler

    return [
        pystray.MenuItem(
            label,
            make_handler(key),
            checked=_radio_check(config_key, key),
            radio=True,
        )
        for label, key in options
    ]


def build_menu():
    toggle_items = [
        pystray.MenuItem(
            label,
            change_hotkey_toggle(label, key),
            checked=_radio_check("hotkey_toggle", key),
            radio=True,
        )
        for label, key in HOTKEY_OPTIONS
    ]

    quit_items = [
        pystray.MenuItem(
            label,
            change_hotkey_quit(label, key),
            checked=_radio_check("hotkey_quit", key),
            radio=True,
        )
        for label, key in QUIT_KEY_OPTIONS
    ]

    model_items = _radio_items(MODEL_OPTIONS, "model", change_model)
    language_items = _radio_items(LANGUAGE_OPTIONS, "language", change_language)
    insert_items = _radio_items(INSERT_MODE_OPTIONS, "insert_mode", change_insert_mode)

    return pystray.Menu(
        pystray.MenuItem(lambda item: f"SOLetrando ({config['model']} / {device})", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Tecla de gravar", pystray.Menu(*toggle_items)),
        pystray.MenuItem("Tecla de encerrar", pystray.Menu(*quit_items)),
        pystray.MenuItem("Modelo", pystray.Menu(*model_items)),
        pystray.MenuItem("Idioma", pystray.Menu(*language_items)),
        pystray.MenuItem("Insercao de texto", pystray.Menu(*insert_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Bip sonoro",
            toggle_beep,
            checked=lambda item: config["beep_enabled"],
        ),
        pystray.MenuItem("Abrir log", on_open_log),
        pystray.MenuItem("Abrir pasta", on_open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Desinstalar SOLetrando...", on_uninstall),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Encerrar", on_tray_quit),
    )


def rebuild_menu():
    if tray_icon is None:
        return
    try:
        tray_icon.menu = build_menu()
        tray_icon.update_menu()
    except Exception as e:
        log(f"Erro ao reconstruir menu: {e}")


def _open_path(path):
    try:
        if IS_WINDOWS:
            os.startfile(str(path))
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        log(f"Erro ao abrir {path}: {e}")


def on_open_log(icon, item):
    if not LOG_PATH.exists():
        notify("Ainda nao ha log para exibir.")
        return
    _open_path(LOG_PATH)


def on_open_folder(icon, item):
    _open_path(DATA_DIR)


def on_uninstall(icon, item):
    """Abre a tela de desinstalacao do Windows para o SOLetrando."""
    try:
        import subprocess
        # Abre Configuracoes > Aplicativos direto na busca do SOLetrando
        subprocess.Popen(["cmd", "/c", "start", "ms-settings:appsfeatures"])
        log("Tela de desinstalacao aberta")
    except Exception as e:
        log(f"Erro ao abrir desinstalacao: {e}")


# =====================================================================
# MAIN
# =====================================================================
def main():
    global tray_icon

    log("=" * 55)
    log("SOLetrando ativo")
    log(f"  Gravar/Parar  = {config['hotkey_toggle']}")
    log(f"  Encerrar      = {config['hotkey_quit']}")
    log(f"  Modelo        = {config['model']} ({device}/{compute_type})")
    log(f"  Idioma        = {config['language'] or 'auto'}")
    log(f"  Insercao      = {config['insert_mode']}")
    log(f"  Dados         = {DATA_DIR}")
    log("=" * 55)

    tray_icon = pystray.Icon(
        name="SOLetrando",
        icon=load_icon("idle"),
        title=idle_title(),
        menu=build_menu(),
    )

    def on_tray_ready(icon):
        """Roda numa thread do pystray, ja com o icone na bandeja.

        Registrar os atalhos aqui (e nao antes) e o que faz um erro de
        registro virar um balao visivel: notify() so aparece depois que o
        icone existe. Antes, um atalho recusado pelo Windows so deixava
        rastro no log."""
        icon.visible = True
        log("Tray icon ativo")
        register_hotkeys()
        start_health_monitor()

    close_splash()
    tray_icon.run(setup=on_tray_ready)
    log("Loop do tray encerrado")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        log(f"Excecao nao tratada: {traceback.format_exc()}")
        fatal(f"O SOLetrando encontrou um erro inesperado:\n\n{e}\n\nDetalhes em: {LOG_PATH}")
