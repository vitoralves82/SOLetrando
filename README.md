# SOLetrando 🎙️

<p align="center">
  <img src="icon.png" alt="SOLetrando" width="128">
</p>

Ditado por voz gratuito, local e offline para Windows — utilizando [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + CUDA/CPU.

Pressione **ScrollLock**, fale, pressione novamente. O texto aparece onde estiver o cursor: Word, Notepad, navegador, qualquer app.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![CUDA](https://img.shields.io/badge/CUDA-opcional-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

> **[English version below](#english)**

---

## Funcionalidades

- **100% local** — sem nuvem, sem assinatura, sem limites
- **Ícone na bandeja do sistema** com indicadores de cor (cinza=ocioso, verde=gravando, amarelo=transcrevendo)
- **Atalhos configuráveis** via menu de clique direito no ícone da bandeja
- **Bip sonoro** ao iniciar/parar gravação
- **Inicialização automática** com o Windows via script VBS ou atalho
- **Executável .exe** independente (não precisa de Python para rodar)
- **Multi-idioma** — Português, Inglês, Espanhol, Francês e mais de 90 idiomas
- **GPU opcional** — usa GPU NVIDIA (CUDA) para velocidade, ou faz fallback para CPU automaticamente

---

## Atalhos (padrão)

| Atalho | Ação |
|---|---|
| **ScrollLock** | Iniciar / Parar gravação e inserir texto |
| **Ctrl+Shift+Q** | Encerrar |

Os atalhos podem ser alterados pelo menu de clique direito no ícone da bandeja. As alterações são salvas automaticamente.

---

## Requisitos

- **Windows 10/11**
- **Python 3.10+** (não necessário se usar o .exe)
- **GPU NVIDIA com CUDA** (opcional — testado na RTX 3060; usa CPU automaticamente se não disponível)
- **Drivers NVIDIA** com suporte a CUDA 11.x ou 12.x (apenas se usar GPU)
- **Microfone**

---

## Instalação

### Opção A: Baixar o executável (recomendado)

1. Vá em [GitHub Releases](https://github.com/vitoralves82/SOLetrando/releases) e baixe o `.zip` da última versão
2. Extraia o conteúdo do `.zip`
3. Execute `install.bat` para criar atalhos no Desktop e Startup automaticamente
4. Ou execute `soletrando.exe` diretamente

Sem necessidade de Python, Git ou terminal.

### Opção B: Rodar a partir do código-fonte

```powershell
git clone https://github.com/vitoralves82/SOLetrando.git
cd SOLetrando
python -m venv .venv
.\.venv\Scripts\activate
```

Instale o PyTorch com CUDA ([pytorch.org](https://pytorch.org/get-started/locally/)):

```powershell
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Execute:

```powershell
python soletrando.py
```

Modo silencioso (sem janela de console — recomendado):

```powershell
.\.venv\Scripts\pythonw.exe soletrando.py
```

Para criar atalhos no Desktop e Startup automaticamente:

```powershell
python install.py
```

### Opção C: Gerar executável .exe a partir do código-fonte

Após instalar a partir do código-fonte (Opção B), execute:

```powershell
build.bat
```

O executável estará em `dist\soletrando\soletrando.exe`. Clique duas vezes para rodar — sem necessidade de Python ou console.

---

## Opções

```
--model     Modelo Whisper: tiny, base, small, medium (padrão), large-v3
--language  Idioma: pt (padrão), en, es, fr, de... ou vazio para detecção automática
```

```powershell
python soletrando.py --model large-v3
python soletrando.py --model small --language en
```

Você também pode alterar o modelo pelo menu do ícone na bandeja (requer reiniciar).

### Modelos — velocidade vs. precisão

| Modelo | VRAM (GPU) / RAM (CPU) | Velocidade | Precisão |
|---|---|---|---|
| `tiny` | ~1 GB | Muito rápido | Baixa |
| `base` | ~1 GB | Rápido | Razoável |
| `small` | ~2 GB | Médio | Boa |
| **`medium`** | **~5 GB** | **Médio** | **Muito boa** |
| `large-v3` | ~10 GB | Mais lento | Excelente |

---

## Inicialização automática com o Windows

### A partir do código-fonte

Copie o `soletrando_startup.vbs` para a pasta de inicialização:

```powershell
copy soletrando_startup.vbs "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\"
```

Edite os caminhos dentro do arquivo `.vbs` se necessário.

### A partir do .exe

Crie um atalho para `dist\soletrando\soletrando.exe` e coloque em:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

---

## Configuração

As configurações são salvas em `soletrando_config.json` (na mesma pasta do script/exe):

```json
{
  "hotkey_toggle": "scroll lock",
  "hotkey_quit": "ctrl+shift+q",
  "model": "medium",
  "language": "pt"
}
```

Você pode editar este arquivo diretamente ou usar o menu do ícone na bandeja.

---

## Menu do Ícone na Bandeja

Clique com o botão direito no ícone "S" na bandeja do sistema:

- **Tecla de gravar** — escolher atalho de gravação (ScrollLock, F8, F9, F10, Pause, Ctrl+Shift+F, etc.)
- **Tecla de encerrar** — escolher atalho para sair
- **Modelo** — escolher modelo Whisper (requer reiniciar)
- **Abrir log** — abrir o arquivo de log
- **Abrir pasta** — abrir a pasta de instalação
- **Encerrar** — fechar o SOLetrando

---

## Estrutura do Projeto

```
soletrando/
├── soletrando.py              # Script principal
├── install.bat                # Instalador (wrapper)
├── install.py                 # Instalador (cria atalhos Desktop/Startup)
├── soletrando_startup.vbs     # Inicialização automática no Windows (VBS)
├── build.bat                  # Script de build (PyInstaller)
├── version.txt                # Versão do aplicativo
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```

---

## Solução de Problemas

| Problema | Solução |
|---|---|
| `No module named 'faster_whisper'` | `pip install faster-whisper` |
| CUDA não detectado | O programa usa CPU automaticamente. Para GPU, verifique os drivers NVIDIA e a versão CUDA do PyTorch |
| Microfone não detectado | `python -c "import sounddevice; print(sounddevice.query_devices())"` |
| Texto não aparece no app | Certifique-se de que o cursor está no app de destino antes de pressionar o atalho |
| "Instance already running" | Delete `%TEMP%\soletrando.lock` ou encerre o `pythonw.exe` |
| Ícone não visível na bandeja | Clique na seta `^` na barra de tarefas para ver ícones ocultos |

---

## Créditos

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Motor de transcrição
- [OpenAI Whisper](https://github.com/openai/whisper) — Modelos de linguagem
- [pystray](https://github.com/moses-palmer/pystray) — Ícone na bandeja do sistema
- [sounddevice](https://python-sounddevice.readthedocs.io/) — Captura de áudio

---

## Licença

MIT

---
---

# <a id="english"></a>English

<p align="center">
  <img src="icon.png" alt="SOLetrando" width="128">
</p>

Free, local, offline voice dictation for Windows — powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + CUDA/CPU.

Press **ScrollLock**, speak, press again. Text appears wherever your cursor is: Word, Notepad, browser, any app.

---

## Features

- **100% local** — no cloud, no subscription, no limits
- **System tray icon** with color indicators (gray=idle, green=recording, yellow=transcribing)
- **Configurable hotkeys** via right-click menu on the tray icon
- **Audio beep** feedback when recording starts/stops
- **Auto-start** with Windows via VBS script or shortcut
- **Standalone .exe** build option (no Python needed to run)
- **Multi-language** — Portuguese, English, Spanish, French, and 90+ languages
- **GPU optional** — runs on NVIDIA GPU (CUDA) for speed, or falls back to CPU automatically

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
- **NVIDIA GPU with CUDA** (optional — tested on RTX 3060; falls back to CPU if unavailable)
- **NVIDIA drivers** with CUDA 11.x or 12.x support (only if using GPU)
- **Microphone**

---

## Installation

### Option A: Download the executable (recommended)

1. Go to [GitHub Releases](https://github.com/vitoralves82/SOLetrando/releases) and download the `.zip` from the latest version
2. Extract the `.zip` contents
3. Run `install.bat` to create Desktop and Startup shortcuts automatically
4. Or run `soletrando.exe` directly

No Python, Git, or terminal needed.

### Option B: Run from source

```powershell
git clone https://github.com/vitoralves82/SOLetrando.git
cd SOLetrando
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
python soletrando.py
```

Headless mode (no console window — recommended):

```powershell
.\.venv\Scripts\pythonw.exe soletrando.py
```

To create Desktop and Startup shortcuts automatically:

```powershell
python install.py
```

### Option C: Build standalone .exe from source

After installing from source (Option B), run:

```powershell
build.bat
```

The executable will be in `dist\soletrando\soletrando.exe`. Double-click to run — no Python or console needed.

---

## Options

```
--model     Whisper model: tiny, base, small, medium (default), large-v3
--language  Language: pt (default), en, es, fr, de... or empty for auto-detect
```

```powershell
python soletrando.py --model large-v3
python soletrando.py --model small --language en
```

You can also change the model via the tray icon menu (requires restart).

### Models — speed vs. accuracy

| Model | VRAM (GPU) / RAM (CPU) | Speed | Accuracy |
|---|---|---|---|
| `tiny` | ~1 GB | Very fast | Low |
| `base` | ~1 GB | Fast | Fair |
| `small` | ~2 GB | Medium | Good |
| **`medium`** | **~5 GB** | **Medium** | **Very good** |
| `large-v3` | ~10 GB | Slower | Excellent |

---

## Auto-start with Windows

### From source

Copy `soletrando_startup.vbs` to the Startup folder:

```powershell
copy soletrando_startup.vbs "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\"
```

Edit the paths inside the `.vbs` file if needed.

### From .exe

Create a shortcut to `dist\soletrando\soletrando.exe` and place it in:

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

---

## Configuration

Settings are saved in `soletrando_config.json` (same folder as the script/exe):

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
- **Encerrar** — quit SOLetrando

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `No module named 'faster_whisper'` | `pip install faster-whisper` |
| CUDA not detected | Program will fall back to CPU automatically. For GPU, check NVIDIA drivers and PyTorch CUDA version |
| Microphone not detected | `python -c "import sounddevice; print(sounddevice.query_devices())"` |
| Text not appearing in app | Make sure cursor is in the target app before pressing the hotkey |
| "Instance already running" | Delete `%TEMP%\soletrando.lock` or kill `pythonw.exe` |
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
