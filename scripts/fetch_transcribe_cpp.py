"""fetch_transcribe_cpp.py - Installa il runtime nativo transcribe.cpp.

Scarica dalla release GitHub di handy-computer/transcribe.cpp:
  * l'archivio nativo Windows (transcribe.dll + DLL ggml) -> cartella `native/`
  * il binding Python (wheel puro, ctypes) -> ambiente Python del pacchetto

Va eseguito SOLO sul PC di sviluppo, con accesso a Internet.

Uso:
    build\\python\\python.exe scripts\\fetch_transcribe_cpp.py --root build/native \\
        --python build\\python\\python.exe
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "handy-computer/transcribe.cpp"
VERSION = "0.4.0"
ASSET_NATIVE = f"transcribe-native-{VERSION}-windows-x86_64-cpu-vulkan.tar.gz"
ASSET_WHEEL = f"transcribe_cpp-{VERSION}-py3-none-any.whl"
BASE = f"https://github.com/{REPO}/releases/download/v{VERSION}"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[transcribe.cpp] scarico {url}")
    with urllib.request.urlopen(url) as resp, open(dest, "wb") as fh:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = resp.read(1024 * 512)
            if not chunk:
                break
            fh.write(chunk)
            done += len(chunk)
            if total:
                pct = 100.0 * done / total
                print(f"\r  {done/1e6:8.1f} / {total/1e6:.1f} MB  ({pct:5.1f}%)", end="")
    print()


def install_native(root: Path) -> None:
    """Estrae transcribe.dll e le DLL ggml nella cartella `root`."""
    dll = root / "transcribe.dll"
    if dll.exists():
        print(f"[transcribe.cpp] libreria nativa gia' presente in {root}, salto.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / ASSET_NATIVE
        _download(f"{BASE}/{ASSET_NATIVE}", archive)
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            root_name = ""
            for m in members:
                if "/" in m.name:
                    root_name = m.name.split("/", 1)[0]
                    break
            tar.extractall(tmp, filter="data")
        src = Path(tmp) / root_name if root_name else Path(tmp)
        if not src.is_dir():
            src = Path(tmp)
        root.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.is_file():
                shutil.copy2(item, root / item.name)
        # licenze dei componenti ggml / miniz / silero
        lic_src = src / "licenses"
        if lic_src.is_dir():
            lic_dst = root / "licenses"
            if lic_dst.exists():
                shutil.rmtree(lic_dst)
            shutil.copytree(lic_src, lic_dst)

    print(f"[transcribe.cpp] libreria nativa installata in {root}")


def install_binding(python: Path) -> None:
    """Installa il binding Python (wheel puro) nell'ambiente indicato."""
    if not python.exists():
        print(f"[transcribe.cpp] Python non trovato: {python}", file=sys.stderr)
        raise SystemExit(2)

    check = subprocess.run(
        [str(python), "-c", "import transcribe_cpp, sys; print(transcribe_cpp.__version__)"],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        print(f"[transcribe.cpp] binding gia' installato (v{check.stdout.strip()}).")
        return

    with tempfile.TemporaryDirectory() as tmp:
        wheel = Path(tmp) / ASSET_WHEEL
        _download(f"{BASE}/{ASSET_WHEEL}", wheel)
        print("[transcribe.cpp] installo il binding Python (--no-deps)")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", "--no-index", str(wheel)],
            check=True,
        )
    print("[transcribe.cpp] binding installato.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("build/native"),
        help="Cartella destinazione della libreria nativa.",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path("build/python/python.exe"),
        help="Python del pacchetto in cui installare il binding.",
    )
    parser.add_argument(
        "--skip-binding", action="store_true", help="Non installare il binding Python."
    )
    args = parser.parse_args()

    install_native(args.root)
    if not args.skip_binding:
        install_binding(args.python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
