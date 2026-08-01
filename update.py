"""
SOLetrando - Atualizador
Consulta o GitHub Releases e baixa a versao mais recente.
"""

import json
import sys
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

REPO = "vitoralves82/SOLetrando"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
VERSION_FILE = "version.txt"
USER_AGENT = "SOLetrando-Updater"


def get_script_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


BASE_DIR = get_script_dir()


def get_local_version():
    vfile = BASE_DIR / VERSION_FILE
    if vfile.exists():
        return vfile.read_text(encoding="utf-8").strip()
    return "0.0.0"


def get_latest_release():
    req = Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
    })
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError, ValueError) as e:
        # Antes so URLError era tratado: um JSON invalido ou um timeout de
        # socket derrubavam o atualizador com traceback.
        print(f"[ERRO] Nao foi possivel consultar o GitHub: {e}")
        return None, None, None

    tag = data.get("tag_name", "").lstrip("v")
    body = data.get("body", "")

    zip_url = None
    for asset in data.get("assets", []):
        if asset["name"].endswith(".zip"):
            zip_url = asset["browser_download_url"]
            break

    return tag, zip_url, body


def download_and_extract(zip_url, dest_dir):
    print("[*] Baixando atualizacao...")
    req = Request(zip_url, headers={"User-Agent": USER_AGENT})
    tmp = Path(tempfile.mkdtemp())
    zip_path = tmp / "update.zip"

    try:
        with urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with zip_path.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r    {pct}% ({downloaded // (1024*1024)} MB)", end="", flush=True)
            print()
    except (URLError, OSError) as e:
        print(f"\n[ERRO] Falha no download: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    print("[*] Extraindo arquivos...")
    try:
        extract_dir = tmp / "extracted"
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
    except (zipfile.BadZipFile, OSError) as e:
        print(f"[ERRO] Arquivo de atualizacao invalido: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return False

    contents = list(extract_dir.iterdir())
    if len(contents) == 1 and contents[0].is_dir():
        source = contents[0]
    else:
        source = extract_dir

    # Config e log agora vivem em %LOCALAPPDATA%\Soletrando, mas mantemos a
    # lista para instalacoes antigas que ainda tenham os arquivos ao lado do exe.
    preserve = {"soletrando_config.json", "soletrando.log"}
    locked = []
    for item in source.rglob("*"):
        rel = item.relative_to(source)
        if rel.name in preserve:
            continue
        target = dest_dir / rel
        try:
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        except OSError as e:
            # Tipicamente o soletrando.exe esta rodando e o Windows bloqueia a
            # escrita. Antes isso abortava no meio, deixando a instalacao
            # misturando arquivos de duas versoes.
            locked.append((rel, e))

    shutil.rmtree(tmp, ignore_errors=True)

    if locked:
        print()
        print(f"  [ERRO] {len(locked)} arquivo(s) nao puderam ser substituidos:")
        for rel, e in locked[:5]:
            print(f"    - {rel}: {e}")
        print("  Feche o SOLetrando (icone na bandeja > Encerrar) e rode o update novamente.")
        return False

    return True


def main():
    print("=" * 50)
    print("  SOLetrando - Atualizador")
    print("=" * 50)
    print()

    local_ver = get_local_version()
    print(f"  Versao local:  {local_ver}")
    print("  Verificando GitHub...", end=" ", flush=True)

    remote_ver, zip_url, release_notes = get_latest_release()

    if remote_ver is None:
        print("\n[ERRO] Nao foi possivel verificar atualizacoes.")
        input("\nPressione Enter para sair...")
        return

    print(f"{remote_ver}")
    print()

    if remote_ver == local_ver:
        print("  Voce ja esta na versao mais recente!")
        input("\nPressione Enter para sair...")
        return

    if not zip_url:
        print(f"  Nova versao disponivel ({remote_ver}), mas nao ha .zip no Release.")
        print(f"  Baixe manualmente: https://github.com/{REPO}/releases/latest")
        input("\nPressione Enter para sair...")
        return

    print(f"  Nova versao disponivel: {remote_ver}")
    if release_notes:
        print(f"\n  Novidades:\n  {release_notes[:300]}")
    print()

    resp = input("  Deseja atualizar agora? (s/n): ").strip().lower()
    if resp not in ("s", "sim", "y", "yes"):
        print("  Atualizacao cancelada.")
        input("\nPressione Enter para sair...")
        return

    if download_and_extract(zip_url, BASE_DIR):
        (BASE_DIR / VERSION_FILE).write_text(remote_ver, encoding="utf-8")
        print()
        print("  [OK] Atualizado para a versao", remote_ver)
        print("  Reinicie o SOLetrando para aplicar.")
    else:
        print("  [ERRO] Falha na atualizacao.")

    input("\nPressione Enter para sair...")


if __name__ == "__main__":
    main()
