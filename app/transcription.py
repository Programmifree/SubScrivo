"""transcription.py - Strutture comuni e accesso al motore di trascrizione.

SubScrivo integra un solo motore: **Parakeet Ultra** in formato GGUF, eseguito
dal runtime nativo transcribe.cpp (ggml). Questo modulo espone i tipi
condivisi (parole, frasi), i percorsi del modello e la factory del motore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import portable

# Callback: (frazione 0..1, dettaglio testuale, secondi elaborati)
ProgressFn = Callable[[float, str, float], None]

# Nome del modello incluso nel pacchetto (unico supportato).
MODEL_FILENAME = "parakeet-ultra-Q8_0.gguf"
MODEL_LABEL = "Parakeet Ultra (GGUF Q8_0)"


class TranscriptionError(RuntimeError):
    pass


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Utterance:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)
    speaker: str = "UNKNOWN"


def model_path(name: str = MODEL_FILENAME) -> Path:
    """Percorso del modello GGUF nella cartella portabile."""
    return portable.GGUF_MODELS_DIR / name


def model_available() -> bool:
    """True se il modello incluso e' presente ed e' un file non vuoto."""
    path = model_path()
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def available_models() -> list[str]:
    """Elenca i modelli GGUF presenti in models/gguf (il primo e' quello incluso)."""
    directory = portable.GGUF_MODELS_DIR
    if not directory.exists():
        return []
    return sorted(p.name for p in directory.glob("*.gguf"))


def create_transcriber(
    model_name: str = MODEL_FILENAME,
    cpu_threads: int = 0,
    backend: str = "cpu",
):
    """Crea il motore di trascrizione (sempre transcribe.cpp + GGUF)."""
    from .transcribe_cpp import TranscribeCppEngine

    return TranscribeCppEngine(
        model_name, cpu_threads=cpu_threads, backend=backend
    )
