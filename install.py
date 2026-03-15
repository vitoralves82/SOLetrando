"""
install.py - Alternativa ao install.bat - requer Python instalado
Cria atalhos no Desktop e no Startup do Windows.
Funciona tanto para o .exe (dist) quanto para codigo-fonte.
Usa apenas stdlib + PowerShell (sem dependencias extras).
"""

import os
import sys
import subprocess
from pathlib import Path


SHORTCUT_NAME = "SOLetrando"


def get_context():
    """Detecta se estamos no modo .exe ou codigo-fonte."""
    script_dir = Path(__file__).resolve().parent
    exe_path = script_dir / "dist" / "soletrando" / "soletrando.exe"

    if exe_path.exists():
        return "exe", exe_path, exe_path.parent
    else:
        # Modo codigo-fonte: usar pythonw.exe do venv ou do sistema
        soletrando_py = script_dir / "soletrando.py"
        venv_pythonw = script_dir / ".venv" / "Scripts" / "pythonw.exe"
        if venv_pythonw.exists():
            target = venv_pythonw
        else:
            target = Path(sys.executable).parent / "pythonw.exe"
            if not target.exists():
                target = Path(sys.executable)
        return "source", target, script_dir, soletrando_py


def create_shortcut(target, shortcut_path, working_dir, arguments="", icon_path=None, description=""):
    """Cria atalho .lnk via PowerShell (sem dependencias COM)."""
    ps_script = (
        '$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{target}"; '
        f'$s.WorkingDirectory = "{working_dir}"; '
        f'$s.Description = "{description}"; '
    )
    if arguments:
        ps_script += f'$s.Arguments = "{arguments}"; '
    if icon_path:
        ps_script += f'$s.IconLocation = "{icon_path}"; '
    ps_script += '$s.Save()'
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        check=True,
        capture_output=True,
    )


def get_desktop_path():
    """Retorna o caminho real do Desktop via Windows API (suporte OneDrive)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Environment]::GetFolderPath('Desktop')"],
            capture_output=True, text=True, check=True,
        )
        desktop = result.stdout.strip()
        if desktop:
            return Path(desktop)
    except Exception:
        pass
    return Path(os.path.expanduser("~")) / "Desktop"


def get_startup_path():
    """Retorna o caminho da pasta Startup do Windows."""
    appdata = os.environ.get("APPDATA", "")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def main():
    print()
    print("=" * 50)
    print("  Instalador do SOLetrando")
    print("=" * 50)
    print()

    ctx = get_context()
    mode = ctx[0]

    if mode == "exe":
        _, target, working_dir = ctx
        arguments = ""
        icon_path = str(target)
        print(f"  Modo: executavel (.exe)")
        print(f"  Target: {target}")
    else:
        _, target, working_dir, soletrando_py = ctx
        arguments = str(soletrando_py)
        icon_path = None
        print(f"  Modo: codigo-fonte")
        print(f"  Target: {target} {soletrando_py.name}")

    print()

    desktop = get_desktop_path()
    startup = get_startup_path()
    errors = []

    # 1. Atalho no Desktop
    try:
        shortcut_path = desktop / f"{SHORTCUT_NAME}.lnk"
        create_shortcut(
            target=str(target),
            shortcut_path=str(shortcut_path),
            working_dir=str(working_dir),
            arguments=arguments,
            icon_path=icon_path,
            description="SOLetrando - Ditado por voz local",
        )
        print(f"  \u2713 Atalho criado no Desktop")
    except Exception as e:
        print(f"  \u2717 Erro ao criar atalho no Desktop: {e}")
        errors.append(("Desktop", e))

    # 2. Atalho no Startup
    try:
        shortcut_path = startup / f"{SHORTCUT_NAME}.lnk"
        create_shortcut(
            target=str(target),
            shortcut_path=str(shortcut_path),
            working_dir=str(working_dir),
            arguments=arguments,
            icon_path=icon_path,
            description="SOLetrando - Ditado por voz local",
        )
        print(f"  \u2713 Atalho criado no Startup (inicializacao automatica)")
    except Exception as e:
        print(f"  \u2717 Erro ao criar atalho no Startup: {e}")
        errors.append(("Startup", e))

    print()
    if not errors:
        print("  \u2713 Instalacao concluida!")
    else:
        print(f"  Instalacao concluida com {len(errors)} erro(s).")
    print()

    # 3. Perguntar se deseja iniciar
    try:
        resp = input("  Deseja iniciar o SOLetrando agora? (s/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        resp = "n"

    if resp in ("s", "sim", "y", "yes"):
        print("  Iniciando SOLetrando...")
        if mode == "exe":
            subprocess.Popen([str(target)], cwd=str(working_dir))
        else:
            subprocess.Popen([str(target), str(soletrando_py)], cwd=str(working_dir))
    else:
        print("  OK. Execute o SOLetrando pelo atalho no Desktop quando quiser.")

    print()


if __name__ == "__main__":
    main()
