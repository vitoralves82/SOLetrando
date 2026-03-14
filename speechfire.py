"""
Speechfire - Ditado por voz local
faster-whisper + CUDA | Alternativa ao Wispr Flow

Atalhos configuraveis via icone na bandeja do sistema.
Configuracoes salvas em speechfire_config.json.
"""

import argparse
import sys
import time
import warnings
import threading
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

warnings.filterwarnings("ignore")

# =====================================================================
# PATHS
# =====================================================================
if getattr(sys, "frozen", False):
    # Rodando como .exe (PyInstaller)
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

LOG_PATH = BASE_DIR / "speechfire.log"
CONFIG_PATH = BASE_DIR / "speechfire_config.json"
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


def load_config():
    try:
        if CONFIG_PATH.exists():
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            # Preenche campos ausentes
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception as e:
        log(f"Erro ao carregar config: {e}")
    return dict(DEFAULT_CONFIG)


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
parser = argparse.ArgumentParser()
parser.add_argument("--model", default=None)
parser.add_argument("--language", default=None)
args = parser.parse_args()

if args.model:
    config["model"] = args.model
if args.language:
    config["language"] = args.language

log(f"Iniciando Speechfire - modelo={config['model']}, idioma={config['language']}")

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
# CARREGAR MODELO
# =====================================================================
log(f"Carregando faster-whisper '{config['model']}' na GPU (float16)...")
model = WhisperModel(config["model"], device="cuda", compute_type="float16")
log("Modelo carregado com sucesso")

# =====================================================================
# ESTADO GLOBAL
# =====================================================================
SAMPLE_RATE = 16000
MIN_DURATION_SECONDS = 0.5
LOCK_FILE = Path(tempfile.gettempdir()) / "speechfire.lock"

is_recording = False
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
            tray_icon.title = "Speechfire - Gravando..."
        elif state == "transcribing":
            tray_icon.icon = make_icon_image(COLOR_TRANSCRIBING, "S")
            tray_icon.title = "Speechfire - Transcrevendo..."
        else:
            tray_icon.icon = make_icon_image(COLOR_IDLE, "S")
            tray_icon.title = f"Speechfire - {config['hotkey_toggle'].title()} para gravar"
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
# SINGLE INSTANCE
# =====================================================================
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
    is_recording = True
    log("REC iniciado")
    update_tray("recording")
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=audio_callback,
        blocksize=1024,
    )
    stream.start()


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
    global is_recording, stream, audio_frames

    if not is_recording:
        return

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
        return

    update_tray("transcribing")
    log("Transcrevendo...")

    try:
        audio_data = np.concatenate(audio_frames, axis=0).flatten().astype(np.float32)
    except Exception as e:
        log(f"Erro ao consolidar audio: {e}")
        update_tray("idle")
        return

    peak = np.max(np.abs(audio_data)) if len(audio_data) else 0
    if peak > 0:
        audio_data = audio_data / peak

    duration = len(audio_data) / SAMPLE_RATE
    log(f"Audio: {duration:.1f}s")

    if duration < MIN_DURATION_SECONDS:
        log("Audio muito curto, ignorando")
        update_tray("idle")
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
        return

    if not text:
        log("Nenhuma fala detectada")
        update_tray("idle")
        return

    log(f"Texto: {text}")
    insert_text(text)
    update_tray("idle")


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
        if not is_recording:
            #beep_start()
            start_recording()
        else:
            stop_and_transcribe()
            #beep_stop()


# =====================================================================
# SHUTDOWN
# =====================================================================
def shutdown():
    global is_recording, stream, tray_icon

    log("Encerrando Speechfire")

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

    os._exit(0)


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
        pystray.MenuItem(f"Speechfire ({config['model']})", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Tecla de gravar", pystray.Menu(*toggle_items)),
        pystray.MenuItem("Tecla de encerrar", pystray.Menu(*quit_items)),
        pystray.MenuItem("Modelo (requer restart)", pystray.Menu(*model_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Abrir log", on_open_log),
        pystray.MenuItem("Abrir pasta", on_open_folder),
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
        os.startfile(str(BASE_DIR))
    except Exception:
        pass


# =====================================================================
# MAIN
# =====================================================================
def main():
    global tray_icon

    ensure_single_instance()

    log("=" * 55)
    log("Speechfire ativo")
    log(f"  Gravar/Parar  = {config['hotkey_toggle']}")
    log(f"  Encerrar      = {config['hotkey_quit']}")
    log(f"  Modelo        = {config['model']}")
    log("=" * 55)

    register_hotkeys()

    tray_icon = pystray.Icon(
        name="Speechfire",
        icon=make_icon_image(COLOR_IDLE, "S"),
        title=f"Speechfire - {config['hotkey_toggle'].title()} para gravar",
        menu=build_menu(),
    )

    log("Tray icon ativo")
    tray_icon.run()


if __name__ == "__main__":
    main()
