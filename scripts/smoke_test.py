"""smoke_test.py - Test end-to-end dell'applicazione senza interfaccia grafica.

Esegue estrazione audio -> trascrizione -> (diarizzazione) -> export e verifica
che i file temporanei vengano rimossi.

Uso (dalla radice del pacchetto, con il Python portabile):
    python\\python.exe scripts\\smoke_test.py samples\\esempio_1_parlante.wav
    python\\python.exe scripts\\smoke_test.py samples\\esempio_2_parlanti.wav --diarize
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import engine, export, portable, transcription  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--diarize", action="store_true", help="Attiva la distinzione parlanti."
    )
    parser.add_argument("--speakers", type=int, default=0, help="0 = automatico")
    parser.add_argument(
        "--asr-backend",
        default="cpu",
        choices=["cpu", "auto"],
        help="Backend per il runtime ggml (transcribe.cpp).",
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "build" / "testdata")
    args = parser.parse_args()

    portable.setup_environment()
    args.out.mkdir(parents=True, exist_ok=True)

    if not transcription.model_available():
        print(
            f"ERRORE: modello {transcription.MODEL_FILENAME} non trovato in "
            "models/gguf/."
        )
        return 1

    options = engine.JobOptions(
        model_name=transcription.MODEL_FILENAME,
        language="auto",
        diarize=args.diarize,
        asr_backend=args.asr_backend,
        num_speakers=args.speakers,
    )

    def on_progress(fraction: float, stage: str, detail: str) -> None:
        print(f"[{fraction * 100:5.1f}%] {stage}: {detail}", flush=True)

    started = time.time()
    result = engine.run_job(args.input, options, on_progress=on_progress)
    elapsed = time.time() - started

    print("\n===== RISULTATO =====")
    print(f"File: {result.source_name}")
    print(f"Durata: {result.duration:.1f}s  |  Lingua: {result.language}")
    print(f"Modello: {result.model}")
    print(f"Diarizzazione: {result.backend}  |  Parlanti: {result.speakers}")
    print(f"Paragrafi: {len(result.paragraphs)}  |  Segmenti: {len(result.segments)}")
    print(f"Tempo totale: {elapsed:.1f}s")
    print()
    for segment in result.paragraphs:
        print(
            f"[{export.format_timestamp(segment['start'])} --> "
            f"{export.format_timestamp(segment['end'])}] {segment['speaker']}"
        )
        print(f"    {segment['text']}")
    print()

    for fmt in ("txt", "md", "srt", "json"):
        path = args.out / f"smoke_result.{fmt}"
        path.write_text(export.render(result, fmt), encoding="utf-8")
        print(f"Scritto: {path}")

    leftover = [p.name for p in portable.TEMP_DIR.iterdir() if p.name != ".running"]
    print(f"\nFile temporanei residui: {leftover}")
    return 0 if not leftover else 2


if __name__ == "__main__":
    raise SystemExit(main())
