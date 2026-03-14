# Speechfire 🔥🎙️

Free, local, offline voice dictation for Windows — powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + CUDA.

Press **ScrollLock**, speak, press again. Text appears wherever your cursor is: Word, Notepad, browser, any app.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![CUDA](https://img.shields.io/badge/CUDA-11.x%2F12.x-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

- **100% local** — no cloud, no subscription, no limits
- **System tray icon** with color indicators (gray=idle, green=recording, yellow=transcribing)
- **Configurable hotkeys** via right-click menu on the tray icon
- **Audio beep** feedback when recording starts/stops
- **Auto-start** with Windows via VBS script or shortcut
- **Standalone .exe** build option (no Python needed to run)
- **Multi-language** — Portuguese, English, Spanish, French, and 90+ languages

---

## Hotkeys (default)

| Shortcut | Action |
|---|---|
| **ScrollLock** | Start / Stop recording and insert text |
| **Ctrl+Shift+Q** | Quit |

Hotkeys can be changed via the tray icon right-click menu. Changes are saved automatically.

---

## Requirements

- **Windows 10/11**
- **Python 3.10+** (not needed if using the .exe build)
- **NVIDIA GPU with CUDA** (tested on RTX 3060)
- **NVIDIA drivers** with CUDA 11.x or 12.x support
- **Microphone**

---

## Installation

### Option A: Run from source

```powershell
git clone https://github.com/YOUR_USER/speechfire.git
cd speechfire
python -m venv .venv
.\.venv\Scripts\activate
```

Install PyTorch with CUDA ([pytorch.org](https://pytorch.org/get-started/locally/)):

```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run:

```powershell
python speechfire.py
```

Headless mode (no console window — recommended):

```powershell
.\.venv\Scripts\pythonw.exe speechfire.py
```

### Option B: Build standalone .exe

After installing from source, run:

```powershell
build.bat
```

The executable will be in `dist\speechfire\speechfire.exe`. Double-click to run — no Python or console needed.

---

## Options

```
--model     Whisper model: tiny, base, small, medium (default), large-v3
--language  Language: pt (default), en, es, fr, de... or empty for auto-detect
```

```powershell
python speechfire.py --model large-v3
python speechfire.py --model small --language en
```

You can also change the model via the tray icon menu (requires restart).

### Models — speed vs. accuracy

| Model | VRAM | Speed | Accuracy |
|---|---|---|---|
| `tiny` | ~1 GB | Very fast | Low |
| `base` | ~1 GB | Fast | Fair |
| `small` | ~2 GB | Medium | Good |
| **`medium`** | **~5 GB** | **Medium** | **Very good** |
| `large-v3` | ~10 GB | Slower | Excellent |

---

## Auto-start with Windows

### From source

Copy `speechfire_startup.vbs` to the Startup folder:

```powershell
copy speechfire_startup.vbs "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\"
```

Edit the paths inside the `.vbs` file if needed.

### From .exe

Create a shortcut to `dist\speechfire\speechfire.exe` and place it in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

---

## Configuration

Settings are saved in `speechfire_config.json` (same folder as the script/exe):

```json
{
  "hotkey_toggle": "scroll lock",
  "hotkey_quit": "ctrl+shift+q",
  "model": "medium",
  "language": "pt"
}
```

You can edit this file directly or use the tray icon menu.

---

## Tray Icon Menu

Right-click the "S" icon in the system tray:

- **Tecla de gravar** — choose recording hotkey (ScrollLock, F8, F9, F10, Pause, Ctrl+Shift+F, etc.)
- **Tecla de encerrar** — choose quit hotkey
- **Modelo** — choose Whisper model (requires restart)
- **Abrir log** — open the log file
- **Abrir pasta** — open the installation folder
- **Encerrar** — quit Speechfire

---

## Project Structure

```
speechfire/
├── speechfire.py              # Main script
├── speechfire_startup.vbs     # Windows auto-start (VBS)
├── build.bat                  # PyInstaller build script
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `No module named 'faster_whisper'` | `pip install faster-whisper` |
| CUDA not detected | Check NVIDIA drivers and PyTorch CUDA version |
| Microphone not detected | `python -c "import sounddevice; print(sounddevice.query_devices())"` |
| Text not appearing in app | Make sure cursor is in the target app before pressing the hotkey |
| "Instance already running" | Delete `%TEMP%\speechfire.lock` or kill `pythonw.exe` |
| Tray icon not visible | Click the `^` arrow in the taskbar to see hidden icons |

---

## Credits

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Transcription engine
- [OpenAI Whisper](https://github.com/openai/whisper) — Language models
- [pystray](https://github.com/moses-palmer/pystray) — System tray icon
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Audio capture

---

## License

MIT
