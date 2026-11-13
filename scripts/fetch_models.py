"""fetch_models.py - Scarica i modelli necessari nella cartella portabile.

Va eseguito SOLO sul PC di sviluppo, con accesso a Internet, usando il Python
portabile dell'applicazione (python\\python.exe). Sul PC di destinazione i
modelli sono gia' presenti e non viene effettuato alcun download.

Modelli inclusi in SubScrivo:
  * handy-computer/parakeet-ultra-gguf  -> models/gguf/parakeet-ultra-Q8_0.gguf
    (trascrizione, pesi CC-BY-4.0, conversione GGUF MIT)
  * hbredin/wespeaker-voxceleb-resnet34-LM -> models/embeddings/
    (embedding per la distinzione parlanti, Apache-2.0)

Uso:
    python\\python.exe scripts\\fetch_models.py --out .
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

GGUF_REPO = "handy-computer/parakeet-ultra-gguf"
GGUF_FILE = "parakeet-ultra-Q8_0.gguf"

WESPEAKER_ONNX_REPO = "hbredin/wespeaker-voxceleb-resnet34-LM"
WESPEAKER_ONNX_FILE = "speaker-embedding.onnx"
WESPEAKER_ONNX_LOCAL = "wespeaker-voxceleb-resnet34-LM.onnx"


def _download_flat(repo: str, remote: str, target: Path) -> None:
    """Scarica un file dal Hub e lo mette in `target` con il nome richiesto."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SystemExit(
            "huggingface-hub non e' installato. Serve solo sul PC di sviluppo:\n"
            "  python\\python.exe -m pip install huggingface-hub"
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        downloaded = hf_hub_download(repo_id=repo, filename=remote, local_dir=tmp)
        shutil.move(downloaded, str(target))


def download_gguf(out_dir: Path) -> None:
    """Scarica il modello di trascrizione Parakeet Ultra (GGUF Q8_0)."""
    target = out_dir / "models" / "gguf" / GGUF_FILE
    if target.exists() and target.stat().st_size > 0:
        print(f"[gguf] {GGUF_FILE}: gia' presente, salto.")
        return
    print(f"[gguf] scarico {GGUF_REPO}/{GGUF_FILE} -> {target}")
    _download_flat(GGUF_REPO, GGUF_FILE, target)
    print(f"[gguf] completato ({target.stat().st_size / 1e6:.0f} MB).")


def download_wespeaker(out_dir: Path) -> None:
    """Scarica il modello di embedding WeSpeaker per la diarizzazione."""
    target = out_dir / "models" / "embeddings" / WESPEAKER_ONNX_LOCAL
    if target.exists() and target.stat().st_size > 0:
        print("[embedding] WeSpeaker ONNX gia' presente, salto.")
        return
    print(f"[embedding] scarico {WESPEAKER_ONNX_REPO}/{WESPEAKER_ONNX_FILE}")
    _download_flat(WESPEAKER_ONNX_REPO, WESPEAKER_ONNX_FILE, target)
    print(f"[embedding] completato -> {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scarica i modelli AI offline.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Radice della cartella portabile (default: cartella del progetto).",
    )
    parser.add_argument(
        "--gguf-only", action="store_true", help="Scarica solo il modello ASR."
    )
    parser.add_argument(
        "--embedding-only", action="store_true", help="Scarica solo WeSpeaker."
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    if args.gguf_only or not args.embedding_only:
        download_gguf(args.out)
    if args.embedding_only or not args.gguf_only:
        download_wespeaker(args.out)

    print("\nModelli pronti in:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
