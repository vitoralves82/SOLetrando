# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# Coleta apenas o necessario para faster-whisper / ctranslate2
fw_datas, fw_binaries, fw_hidden = collect_all('faster_whisper')
ct_datas, ct_binaries, ct_hidden = collect_all('ctranslate2')

hiddenimports = [
    'faster_whisper',
    'ctranslate2',
    'sounddevice',
    'keyboard',
    'pystray',
    'pystray._win32',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'numpy',
] + fw_hidden + ct_hidden

datas = fw_datas + ct_datas
binaries = fw_binaries + ct_binaries

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
]

a = Analysis(
    ['speechfire.py'],
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='speechfire',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='NONE',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='speechfire',
)
