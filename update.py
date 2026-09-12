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
from pathlib import PurePosixPath
from urllib.request import urlopen, Request
from urllib.error import URLError

REPO = "vitoralves82/SOLetrando"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
VERSION_FILE = "version.txt"
USER_AGENT = "SOLetrando-Updater"
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_SIZE = 2 * 1024 * 1024 * 1024


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


def _safe_member_path(member_name):
    """Normaliza um nome do ZIP e rejeita caminhos fora do destino."""
    normalized = member_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or path.anchor or ".." in path.parts:
        raise ValueError(f"Caminho inseguro no ZIP: {member_name}")
    if not path.parts or any(part in ("", ".") for part in path.parts):
        raise ValueError(f"Caminho invalido no ZIP: {member_name}")
    if ":" in path.parts[0]:
        raise ValueError(f"Caminho absoluto do Windows no ZIP: {member_name}")
    return Path(*path.parts)


def safe_extract_archive(zf, extract_dir):
    """Extrai um ZIP sem permitir traversal, links ou volume excessivo."""
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_FILES:
        raise ValueError("ZIP contem arquivos demais")

    total_size = sum(member.file_size for member in members)
    if total_size > MAX_ARCHIVE_SIZE:
        raise ValueError("ZIP descompactado excede o limite de 2 GB")

    extract_root = extract_dir.resolve()
    for member in members:
        relative = _safe_member_path(member.filename)
        target = (extract_root / relative).resolve()
        if target != extract_root and extract_root not in target.parents:
            raise ValueError(f"Arquivo escaparia do destino: {member.filename}")

        # Bits superiores de external_attr guardam o modo Unix. Links
        # simbolicos nao sao necessarios no pacote e podem apontar para fora.
        file_type = (member.external_attr >> 16) & 0o170000
        if file_type == 0o120000:
            raise ValueError(f"Link simbolico nao permitido: {member.filename}")

        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member, "r") as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)


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
            safe_extract_archive(zf, extract_dir)
    except (zipfile.BadZipFile, OSError, ValueError) as e:
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
