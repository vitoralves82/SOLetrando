"""
SOLetrando - Ditado por voz local
faster-whisper + CUDA/CPU | Alternativa ao Wispr Flow

Atalhos configuraveis via icone na bandeja do sistema.
Configuracoes salvas em soletrando_config.json.
"""

import argparse
import sys
import time
import warnings
import threading
import os
import json
import tempfile
import atexit
from pathlib import Path
from datetime import datetime

# =====================================================================
# SPLASH SCREEN (fecha automaticamente ao carregar o modelo)
# =====================================================================
_splash = None

def show_splash():
    global _splash
    try:
        import tkinter as tk
        _splash = tk.Tk()
        _splash.overrideredirect(True)
        _splash.attributes("-topmost", True)
        w, h = 300, 100
        x = (_splash.winfo_screenwidth() - w) // 2
        y = (_splash.winfo_screenheight() - h) // 2
        _splash.geometry(f"{w}x{h}+{x}+{y}")
        _splash.configure(bg="#1a1a2e")
        lbl = tk.Label(
            _splash,
            text="SOLetrando\nCarregando modelo...",
            font=("Segoe UI", 14),
            fg="white",
            bg="#1a1a2e",
        )
        lbl.pack(expand=True)
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

MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = DATA_DIR / "soletrando.log"
CONFIG_PATH = DATA_DIR / "soletrando_config.json"
HAS_CONSOLE = sys.stdout is not None and hasattr(sys.stdout, "write")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
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


# =====================================================================
# CONFIG (hotkeys + modelo)
# =====================================================================
DEFAULT_CONFIG = {
    "hotkey_toggle": "scroll lock",
    "hotkey_quit": "ctrl+shift+q",
    "model": "medium",
    "language": "pt",
    "beep_enabled": False,
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
    ("tiny", "tiny"),
    ("base", "base"),
    ("small", "small"),
    ("medium", "medium"),
    ("large-v3", "large-v3"),
]

VALID_HOTKEY_TOGGLE_KEYS = {key for _, key in HOTKEY_OPTIONS}
VALID_HOTKEY_QUIT_KEYS = {"ctrl+shift+q", "ctrl+alt+q", "ctrl+shift+e"}
VALID_MODEL_KEYS = {key for _, key in MODEL_OPTIONS}


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
    if not isinstance(normalized.get("beep_enabled"), bool):
        normalized["beep_enabled"] = DEFAULT_CONFIG["beep_enabled"]
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
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        log(f"Config salva: {cfg}")
    except Exception as e:
        log(f"Erro ao salvar config: {e}")


config = load_config()

# =====================================================================
# ARGUMENTOS (override da config)
# =====================================================================
parser = argparse.ArgumentParser(description="SOLetrando - Ditado por voz local")
parser.add_argument("--model", default=None, help="Modelo Whisper: tiny, base, small, medium (padrao), large-v3")
parser.add_argument("--language", default=None, help="Idioma: pt (padrao), en, es, fr, de... ou vazio para deteccao automatica")
args = parser.parse_args()

if args.model:
    if args.model in VALID_MODEL_KEYS:
        config["model"] = args.model
    else:
        log(f"Modelo invalido via argumento ({args.model}), usando '{config['model']}'")
if args.language:
    config["language"] = args.language

log(f"Iniciando SOLetrando - modelo={config['model']}, idioma={config['language']}")

# =====================================================================
# IMPORTS PESADOS
# =====================================================================
import numpy as np
from faster_whisper import WhisperModel
import sounddevice as sd
import keyboard
from PIL import Image, ImageDraw, ImageFont
import pystray

# =====================================================================
# DETECCAO DE GPU (sem torch)
# =====================================================================
import ctypes

def _cuda_available():
    try:
        ctypes.CDLL("nvcuda.dll")
        return True
    except OSError:
        return False

if _cuda_available():
    device = "cuda"
    compute_type = "float16"
    log(f"Carregando faster-whisper '{config['model']}' na GPU (float16)...")
else:
    device = "cpu"
    compute_type = "int8"
    log(f"GPU nao disponivel. Carregando faster-whisper '{config['model']}' na CPU (int8)...")

# =====================================================================
# DOWNLOAD/CARREGAMENTO DO MODELO COM PROGRESSO
# =====================================================================
import tkinter as tk
from tkinter import ttk
from huggingface_hub import scan_cache_dir


def is_model_cached(model_name):
    """Verifica se o modelo ja esta no cache do huggingface_hub."""
    try:
        full_name = f"Systran/faster-whisper-{model_name}"
        cache_info = scan_cache_dir()
        for repo in cache_info.repos:
            if repo.repo_id == full_name:
                return True
    except Exception:
        pass
    return False


def load_model_with_progress(model_name, device, compute_type):
    """Carrega modelo, mostrando janela de progresso se precisar baixar."""
    if is_model_cached(model_name):
        log(f"Modelo '{model_name}' encontrado em cache")
        return WhisperModel(model_name, device=device, compute_type=compute_type)

    # Modelo nao esta em cache — mostrar janela de download
    log(f"Modelo '{model_name}' nao encontrado, iniciando download...")

    result = {"model": None, "error": None}

    def download_thread():
        try:
            result["model"] = WhisperModel(model_name, device=device, compute_type=compute_type)
        except Exception as e:
            result["error"] = e

    # Janela tkinter
    root = tk.Tk()
    root.title("SOLetrando")
    root.geometry("420x150")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack(fill="both", expand=True)

    label = tk.Label(frame, text=f"Baixando modelo '{model_name}'...\nIsso acontece apenas na primeira vez.",
                     justify="center", font=("Segoe UI", 10))
    label.pack(pady=(0, 15))

    progress = ttk.Progressbar(frame, mode="indeterminate", length=350)
    progress.pack()
    progress.start(15)

    thread = threading.Thread(target=download_thread, daemon=True)
    thread.start()

    def check_thread():
        if thread.is_alive():
            root.after(200, check_thread)
        else:
            root.destroy()

    root.after(200, check_thread)
    root.protocol("WM_DELETE_WINDOW", lambda: None)  # Impedir fechar
    root.mainloop()

    if result["error"]:
        raise result["error"]

    return result["model"]


# =====================================================================
# SINGLE INSTANCE
# =====================================================================
LOCK_FILE = Path(tempfile.gettempdir()) / "soletrando.lock"


def ensure_single_instance():
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            os.kill(old_pid, 0)
            log(f"Ja existe instancia rodando (PID={old_pid}). Encerrando.")
            sys.exit(0)
        except Exception:
            pass
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def cleanup_lock():
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


atexit.register(cleanup_lock)

ensure_single_instance()
model = load_model_with_progress(config["model"], device, compute_type)
log("Modelo carregado com sucesso")

# =====================================================================
# ESTADO GLOBAL
# =====================================================================
SAMPLE_RATE = 16000
MIN_DURATION_SECONDS = 0.5

is_recording = False
is_transcribing = False
audio_frames = []
stream = None
toggle_lock = threading.Lock()
last_toggle_time = 0.0
DEBOUNCE_SECONDS = 0.35
tray_icon = None
current_hotkey_toggle = None
current_hotkey_quit = None


# =====================================================================
# TRAY ICON
# =====================================================================
COLOR_IDLE = "#888888"
COLOR_REC = "#00C853"
COLOR_TRANSCRIBING = "#FFC107"


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


def update_tray(state):
    global tray_icon
    if tray_icon is None:
        return
    try:
        if state == "recording":
            tray_icon.icon = make_icon_image(COLOR_REC, "S")
            tray_icon.title = "SOLetrando - Gravando..."
        elif state == "transcribing":
            tray_icon.icon = make_icon_image(COLOR_TRANSCRIBING, "S")
            tray_icon.title = "SOLetrando - Transcrevendo..."
        else:
            tray_icon.icon = make_icon_image(COLOR_IDLE, "S")
            tray_icon.title = f"SOLetrando - {config['hotkey_toggle'].title()} para gravar"
    except Exception as e:
        log(f"Erro ao atualizar tray: {e}")


# =====================================================================
# HOTKEY MANAGEMENT
# =====================================================================
def register_hotkeys():
    global current_hotkey_toggle, current_hotkey_quit

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

    current_hotkey_toggle = keyboard.add_hotkey(config["hotkey_toggle"], toggle)
    current_hotkey_quit = keyboard.add_hotkey(config["hotkey_quit"], shutdown)
    log(f"Hotkeys registradas: toggle={config['hotkey_toggle']}, quit={config['hotkey_quit']}")


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


def is_current_toggle(key):
    def check(item):
        return config["hotkey_toggle"] == key
    return check


def is_current_quit(key):
    def check(item):
        return config["hotkey_quit"] == key
    return check


def is_current_model(model_key):
    def check(item):
        return config["model"] == model_key
    return check


# =====================================================================
# BEEPS
# =====================================================================
def beep_start():
    try:
        import winsound
        winsound.Beep(800, 120)
    except Exception:
        pass


def beep_stop():
    try:
        import winsound
        winsound.Beep(450, 120)
    except Exception:
        pass


def toggle_beep(icon, item):
    config["beep_enabled"] = not config["beep_enabled"]
    save_config(config)
    log(f"Bip sonoro {'ativado' if config['beep_enabled'] else 'desativado'}")


# =====================================================================
# AUDIO
# =====================================================================
def audio_callback(indata, frames, time_info, status):
    global audio_frames, is_recording
    if is_recording:
        audio_frames.append(indata.copy())


def start_recording():
    global is_recording, audio_frames, stream
    if is_recording:
        return
    audio_frames = []
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
        stream = None
        log(f"Falha ao iniciar gravacao: {e}")
        update_tray("idle")
        return

    is_recording = True
    log("REC iniciado")
    update_tray("recording")


# =====================================================================
# INSERIR TEXTO
# =====================================================================
def insert_text(text):
    try:
        keyboard.write(text, delay=0.008)
        log("Texto inserido")
        return True
    except Exception as e:
        log(f"Falha ao inserir texto: {e}")
        return False


# =====================================================================
# TRANSCREVER
# =====================================================================
def stop_and_transcribe():
    global is_recording, stream, audio_frames, is_transcribing

    if not is_recording:
        return

    is_transcribing = True

    is_recording = False

    try:
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None
    except Exception as e:
        log(f"Erro ao fechar stream: {e}")
        stream = None

    if not audio_frames:
        log("Nenhum audio capturado")
        update_tray("idle")
        is_transcribing = False
        return

    update_tray("transcribing")
    log("Transcrevendo...")

    try:
        audio_data = np.concatenate(audio_frames, axis=0).flatten().astype(np.float32)
    except Exception as e:
        log(f"Erro ao consolidar audio: {e}")
        update_tray("idle")
        is_transcribing = False
        return

    peak = np.max(np.abs(audio_data)) if len(audio_data) else 0

    # Protecao contra audio silencioso
    if peak < 0.01:
        log("Audio muito silencioso, ignorando")
        update_tray("idle")
        is_transcribing = False
        return

    if peak > 0:
        audio_data = audio_data / peak

    duration = len(audio_data) / SAMPLE_RATE
    log(f"Audio: {duration:.1f}s")

    if duration < MIN_DURATION_SECONDS:
        log("Audio muito curto, ignorando")
        update_tray("idle")
        is_transcribing = False
        return

    try:
        segments, info = model.transcribe(
            audio_data,
            language=config["language"] if config["language"] else None,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
    except Exception as e:
        log(f"Erro na transcricao: {e}")
        update_tray("idle")
        is_transcribing = False
        return

    if not text:
        log("Nenhuma fala detectada")
        update_tray("idle")
        is_transcribing = False
        return

    log(f"Texto: {text}")
    insert_text(text)
    update_tray("idle")
    is_transcribing = False


# =====================================================================
# TOGGLE
# =====================================================================
def toggle():
    global last_toggle_time

    now = time.time()
    if (now - last_toggle_time) < DEBOUNCE_SECONDS:
        return
    last_toggle_time = now

    with toggle_lock:
        if is_transcribing:
            log("Transcricao em andamento, aguarde...")
            return
        if not is_recording:
            if config["beep_enabled"]:
                beep_start()
            start_recording()
        else:
            if config["beep_enabled"]:
                beep_stop()
            threading.Thread(target=stop_and_transcribe, daemon=True).start()


# =====================================================================
# SHUTDOWN
# =====================================================================
def shutdown():
    global is_recording, stream, tray_icon

    log("Encerrando SOLetrando")

    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        pass

    try:
        if stream is not None:
            stream.stop()
            stream.close()
            stream = None
    except Exception:
        pass

    is_recording = False
    cleanup_lock()

    if tray_icon is not None:
        try:
            tray_icon.stop()
        except Exception:
            pass

    sys.exit(0)


def on_tray_quit(icon, item):
    shutdown()


# =====================================================================
# BUILD TRAY MENU
# =====================================================================
def build_menu():
    # Submenu: Tecla de gravar
    toggle_items = [
        pystray.MenuItem(
            label,
            change_hotkey_toggle(label, key),
            checked=is_current_toggle(key),
            radio=True,
        )
        for label, key in HOTKEY_OPTIONS
    ]

    # Submenu: Tecla de encerrar
    quit_key_options = [
        ("Ctrl+Shift+Q", "ctrl+shift+q"),
        ("Ctrl+Alt+Q", "ctrl+alt+q"),
        ("Ctrl+Shift+E", "ctrl+shift+e"),
    ]
    quit_items = [
        pystray.MenuItem(
            label,
            change_hotkey_quit(label, key),
            checked=is_current_quit(key),
            radio=True,
        )
        for label, key in quit_key_options
    ]

    # Submenu: Modelo (informativo — requer restart)
    def change_model_handler(model_key):
        def handler(icon, item):
            change_model(model_key)
        return handler

    model_items = [
        pystray.MenuItem(
            label,
            change_model_handler(key),
            checked=is_current_model(key),
            radio=True,
        )
        for label, key in MODEL_OPTIONS
    ]

    return pystray.Menu(
        pystray.MenuItem(f"SOLetrando ({config['model']})", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Tecla de gravar", pystray.Menu(*toggle_items)),
        pystray.MenuItem("Tecla de encerrar", pystray.Menu(*quit_items)),
        pystray.MenuItem("Modelo (requer restart)", pystray.Menu(*model_items)),
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


def change_model(model_key):
    config["model"] = model_key
    save_config(config)
    log(f"Modelo alterado para '{model_key}' (efetivo no proximo restart)")


def on_open_log(icon, item):
    try:
        os.startfile(str(LOG_PATH))
    except Exception:
        pass


def on_open_folder(icon, item):
    try:
        os.startfile(str(DATA_DIR))
    except Exception:
        pass


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
    log(f"  Modelo        = {config['model']}")
    log(f"  Dados         = {DATA_DIR}")
    log("=" * 55)

    register_hotkeys()

    tray_icon = pystray.Icon(
        name="SOLetrando",
        icon=make_icon_image(COLOR_IDLE, "S"),
        title=f"SOLetrando - {config['hotkey_toggle'].title()} para gravar",
        menu=build_menu(),
    )

    close_splash()
    log("Tray icon ativo")
    tray_icon.run()


if __name__ == "__main__":
    main()
