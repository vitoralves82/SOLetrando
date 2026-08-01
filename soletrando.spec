# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

# Coleta apenas o necessario para faster-whisper / ctranslate2
fw_datas, fw_binaries, fw_hidden = collect_all('faster_whisper')
ct_datas, ct_binaries, ct_hidden = collect_all('ctranslate2')

# onnxruntime NAO era coletado antes. O faster-whisper o importa em tempo de
# execucao, dentro da funcao do VAD (Silero), entao o PyInstaller nao
# conseguia detectar a dependencia sozinho. Resultado: no .exe o
# vad_filter=True falhava com "requires the onnxruntime package" e a
# transcricao inteira era abortada.
ort_datas, ort_binaries, ort_hidden = collect_all('onnxruntime')

hiddenimports = [
    'faster_whisper',
    'ctranslate2',
    'onnxruntime',
    'sounddevice',
    'keyboard',
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageTk',
    'numpy',
    'huggingface_hub',
    'tkinter',
    'tkinter.ttk',
] + fw_hidden + ct_hidden + ort_hidden

datas = fw_datas + ct_datas + ort_datas
datas += [('version.txt', '.'), ('soletrando.ico', '.'), ('icon_idle.png', '.'), ('icon_recording.png', '.'), ('icon_transcribing.png', '.')]
binaries = fw_binaries + ct_binaries + ort_binaries

# Evita hooks desnecessarios que estao quebrando seu build
excludes = [
    'matplotlib',
    'matplotlib_inline',
    'kiwisolver',
    'torch',
    'torchvision',
    'torchaudio',
    'tensorboard',
    'torch.utils.tensorboard',
    'IPython',
    'jupyter_client',
    'jupyter_core',
    'rich',
    'pygments',
    'anyio',
    'sniffio',
    'tensorflow',
    'pytest',
    'setuptools',
]

a = Analysis(
    ['soletrando.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# UPX desligado de proposito:
#  1) compactar DLLs de CUDA/cuDNN/oneDNN e uma causa conhecida de crash
#     silencioso na inicializacao;
#  2) binarios compactados com UPX disparam muito mais falso-positivo de
#     antivirus — algo critico para um app que instala hook de teclado.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='soletrando',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='soletrando.ico' if os.path.exists('soletrando.ico') else 'NONE',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='soletrando',
)
