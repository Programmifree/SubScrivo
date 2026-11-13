"""bench_models.py - Misura velocita' e qualita' del modello incluso.

Esegue la pipeline su un file audio con Parakeet Ultra (GGUF) e riporta
tempi, testo e WER rispetto a un testo di riferimento.

Uso:
    python\\python.exe scripts\\bench_models.py "PERCORSO\\audio.mp3" \\
        --ref "build\\testdata\\ref.txt" --out-dir build\\testdata\\bench
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import media, portable, transcription  # noqa: E402


# ---------------------------------------------------------------------------
# WER minimale (normalizzazione + distanza di Levenshtein a parole)
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s']", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower().replace("’", "'")
    text = _PUNCT_RE.sub(" ", text)
    return [w for w in _SPACE_RE.split(text) if w]


def wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate in percentuale (100 = tutto sbagliato)."""
    ref = normalize_words(reference)
    hyp = normalize_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 100.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cur[j] = min(
                prev[j] + 1,  # cancellazione
                cur[j - 1] + 1,  # inserimento
                prev[j - 1] + (r != h),  # sostituzione
            )
        prev = cur
    return 100.0 * prev[len(hyp)] / len(ref)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--language", default="auto")
    parser.add_argument(
        "--backend",
        default="cpu",
        help="Backend per il runtime ggml: cpu (default) | auto",
    )
    parser.add_argument("--ref", type=Path, default=None, help="Testo di riferimento")
    parser.add_argument(
        "--out-dir", type=Path, default=REPO_ROOT / "build" / "testdata" / "bench"
    )
    parser.add_argument("--keep-wav", action="store_true")
    args = parser.parse_args()

    portable.setup_environment()

    if not args.input.exists():
        print(f"File non trovato: {args.input}")
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"File: {args.input}")
    duration = media.probe_duration(args.input)
    print(f"Durata: {duration:.1f} s\n")

    # Estrazione audio (riusa media.py)
    portable.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = portable.TEMP_DIR / f"bench_{args.input.stem}.wav"
    media.extract_audio(args.input, wav_path, duration=duration)

    reference = ""
    if args.ref and args.ref.exists():
        reference = args.ref.read_text(encoding="utf-8")
        print(f"Testo di riferimento: {args.ref} ({len(reference)} caratteri)\n")

    engine = transcription.create_transcriber(
        transcription.MODEL_FILENAME, backend=args.backend
    )
    t0 = time.time()
    utterances, meta = engine.transcribe(
        wav_path, duration=duration, language=args.language
    )
    elapsed = time.time() - t0

    text = " ".join(u.text for u in utterances).strip()
    out_txt = args.out_dir / "parakeet-ultra.txt"
    out_txt.write_text(text, encoding="utf-8")
    out_json = args.out_dir / "parakeet-ultra.segments.json"
    out_json.write_text(
        json.dumps(
            [
                {"start": u.start, "end": u.end, "text": u.text, "speaker": u.speaker}
                for u in utterances
            ],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    row = {
        "engine": transcription.MODEL_LABEL,
        "seconds": round(elapsed, 1),
        "ratio": round(elapsed / duration, 3) if duration else 0,
        "language": meta.get("language"),
        "segments": len(utterances),
        "words": len(text.split()),
        "chars": len(text),
        "text_file": str(out_txt),
    }
    if reference:
        row["wer_vs_ref"] = round(wer(reference, text), 2)

    print(f"tempo: {elapsed:.1f} s  ({row['ratio']:.2f}x del tempo audio)")
    print(f"lingua: {meta.get('language')}  segmenti: {len(utterances)}")
    print(f"testo: {out_txt}")
    if reference:
        print(f"WER vs riferimento: {row['wer_vs_ref']}%")

    (args.out_dir / "summary.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.keep_wav:
        try:
            wav_path.unlink()
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
