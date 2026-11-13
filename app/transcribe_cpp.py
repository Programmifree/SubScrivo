"""transcribe_cpp.py - Trascrizione con transcribe.cpp (modello GGUF, ggml).

SubScrivo include un solo modello: **Parakeet Ultra** (GGUF Q8_0), eseguito
dalla libreria nativa ``transcribe.dll`` presente in ``native/``. Parakeet
Ultra restituisce timestamp per token/parola, quindi l'intero file viene
trascritto in una sola passata e segmentato dal modello sulle pause.

Il runtime gira su CPU con ggml; il backend Vulkan viene usato solo se
l'utente sceglie l'accelerazione automatica e la scheda video e' compatibile.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

from . import applog, portable
from .transcription import (
    MODEL_FILENAME,
    ProgressFn,
    TranscriptionError,
    Utterance,
    Word,
)

_MODEL_CACHE: dict[str, object] = {}
_BINDING_LOCK = threading.Lock()
_BINDING = None


class TranscribeCppError(TranscriptionError):
    pass


# ---------------------------------------------------------------------------
# Caricamento della libreria nativa
# ---------------------------------------------------------------------------

def native_dir() -> Path:
    """Cartella che contiene transcribe.dll e le DLL ggml."""
    override = os.environ.get("SUBSCRIVO_NATIVE_DIR")
    if override:
        return Path(override)
    for candidate in (portable.NATIVE_DIR, portable.ROOT / "native"):
        if (candidate / "transcribe.dll").exists():
            return candidate
    return portable.NATIVE_DIR


def library_path() -> Optional[Path]:
    lib = native_dir() / "transcribe.dll"
    return lib if lib.exists() else None


def _install_log_sink(tc) -> None:
    """Porta i log nativi di transcribe.cpp nel log dell'app."""
    try:
        logger = applog.get()
    except Exception:  # noqa: BLE001
        return

    def _sink(level: int, message: str) -> None:
        text = (message or "").rstrip()
        if not text:
            return
        try:
            if level >= 3:  # ERROR
                logger.warning("transcribe.cpp: %s", text)
            else:
                logger.debug("transcribe.cpp: %s", text)
        except Exception:  # noqa: BLE001, S110
            pass

    try:
        tc.set_log_callback(_sink)
    except Exception:  # noqa: BLE001, S110
        pass


def _load_binding(backend: str = "cpu"):
    """Importa il binding Python di transcribe.cpp puntando alla DLL locale."""
    global _BINDING
    with _BINDING_LOCK:
        if _BINDING is not None:
            return _BINDING

        lib = library_path()
        if lib is None:
            raise TranscribeCppError(
                "Libreria nativa transcribe.dll non trovata in "
                f"'{native_dir()}'. Il pacchetto non e' completo."
            )

        # Le DLL ggml devono essere trovabili dal loader di Windows.
        directory = str(lib.parent)
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(directory)  # noqa: B010
            except OSError:
                pass
        os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
        os.environ["TRANSCRIBE_LIBRARY"] = str(lib)

        # Con backend "cpu" non registriamo nemmeno Vulkan: meno memoria usata,
        # nessun rumore di inizializzazione driver e nessun rischio di OOM.
        if str(backend).lower() == "cpu":
            os.environ.setdefault("TRANSCRIBE_BACKENDS", "cpu")

        try:
            import transcribe_cpp
        except Exception as exc:  # noqa: BLE001
            raise TranscribeCppError(
                f"Impossibile caricare il binding transcribe-cpp: {exc}"
            ) from exc

        _install_log_sink(transcribe_cpp)

        applog.get().info(
            "transcribe.cpp caricato (versione %s, libreria %s)",
            getattr(transcribe_cpp, "__version__", "?"),
            lib,
        )
        _BINDING = transcribe_cpp
        return _BINDING


def model_path(name: str = MODEL_FILENAME) -> Path:
    return portable.GGUF_MODELS_DIR / name


# ---------------------------------------------------------------------------
# Motore
# ---------------------------------------------------------------------------

class TranscribeCppEngine:
    """Motore di trascrizione basato su transcribe.cpp + Parakeet Ultra."""

    def __init__(
        self,
        model_name: str = MODEL_FILENAME,
        cpu_threads: int = 0,
        backend: str = "cpu",
    ) -> None:
        self._name = model_name
        self._file = model_path(model_name)
        if not self._file.exists():
            raise TranscribeCppError(
                f"Il modello '{model_name}' non e' presente in models/gguf. "
                "Il pacchetto non e' completo: estrai di nuovo lo ZIP per intero."
            )
        self._cpu_threads = cpu_threads
        # "cpu" e' il default: il pacchetto e' pensato per girare senza GPU.
        # "auto" lascia scegliere a transcribe.cpp (Vulkan, se il driver c'e').
        self._backend = backend or "cpu"

    # -- caricamento ------------------------------------------------------
    def _load(self):
        key = f"{self._name}|{self._cpu_threads}|{self._backend}"
        cached = _MODEL_CACHE.get(key)
        if cached is not None:
            return cached

        tc = _load_binding(self._backend)
        applog.get().info(
            "Caricamento modello GGUF '%s' (backend %s)", self._name, self._backend
        )
        started = time.time()
        try:
            model = tc.Model(str(self._file), backend=self._backend)
        except Exception as exc:  # noqa: BLE001
            raise TranscribeCppError(
                f"Impossibile caricare il modello '{self._name}': {exc}"
            ) from exc
        applog.get().info("Modello caricato in %.1f s", time.time() - started)
        _MODEL_CACHE[key] = model
        return model

    # -- trascrizione -----------------------------------------------------
    def transcribe(
        self,
        audio_path: Path,
        duration: float,
        language: Optional[str] = None,
        cancel: Optional[threading.Event] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> tuple[list[Utterance], dict]:
        import soundfile as sf

        model = self._load()

        audio, sr = sf.read(str(audio_path), dtype="float32", always_2d=True)
        audio = audio.mean(axis=1).astype(np.float32)
        if sr != 16000:
            target_len = int(round(len(audio) * 16000.0 / sr))
            if target_len > 0:
                x_old = np.linspace(0.0, 1.0, len(audio), endpoint=False)
                x_new = np.linspace(0.0, 1.0, target_len, endpoint=False)
                audio = np.interp(x_new, x_old, audio).astype(np.float32)
        total = duration if duration > 0 else len(audio) / 16000.0

        caps = getattr(model, "capabilities", None)
        kind = str(getattr(caps, "max_timestamp_kind", "none") or "none")
        if kind == "none":
            raise TranscribeCppError(
                "Il modello GGUF non fornisce timestamp: SubScrivo richiede "
                "Parakeet Ultra (o un modello con timestamp per parola)."
            )

        if on_progress:
            on_progress(0.0, "Avvio decodifica", 0.0)

        with model.session(n_threads=self._cpu_threads) as session:
            result = self._run_with_cancel(
                session, audio, language, cancel, on_progress=on_progress
            )

        utterances = self._result_to_utterances(result)
        if on_progress:
            on_progress(1.0, "Trascrizione completata", total)
        return utterances, {
            "language": result.language or "auto",
            "duration": total,
        }

    # -- esecuzione con cancellazione ------------------------------------
    def _run_with_cancel(
        self, session, audio: np.ndarray, language, cancel, on_progress=None
    ):
        """Esegue session.run() e permette l'annullamento da un altro thread."""
        # "auto" non e' un codice lingua: in quel caso il modello decide da se'.
        lang = None
        if language and str(language).lower() not in ("auto", "", "none"):
            lang = str(language)

        if cancel is None:
            return session.run(audio, language=lang)

        # Gia' annullato prima di iniziare: non sprecare lavoro.
        if cancel.is_set():
            raise InterruptedError("Trascrizione annullata")

        stop = threading.Event()
        started = time.monotonic()
        last_tick = started

        def _watcher() -> None:
            nonlocal last_tick
            while not stop.wait(0.25):
                now = time.monotonic()
                # La decodifica non espone un avanzamento nativo: mostriamo
                # almeno il tempo trascorso invece di una finestra ferma.
                if on_progress is not None and now - last_tick >= 2.0:
                    last_tick = now
                    try:
                        on_progress(
                            0.0,
                            "Trascrizione",
                            f"In corso da {_fmt_hms(now - started)} "
                            "(Interrompi per annullare)",
                        )
                    except Exception:  # noqa: BLE001, S110
                        pass
                if cancel.is_set():
                    try:
                        session.cancel()
                    except Exception:  # noqa: BLE001, S110
                        pass
                    return

        watcher = threading.Thread(target=_watcher, daemon=True)
        watcher.start()
        try:
            return session.run(audio, language=lang)
        except Exception as exc:  # noqa: BLE001
            # transcribe.cpp interrompe con Aborted: per l'app e' un annullamento.
            if cancel.is_set() and type(exc).__name__ == "Aborted":
                raise InterruptedError("Trascrizione annullata") from exc
            raise
        finally:
            stop.set()
            watcher.join(timeout=1.0)

    # -- conversione del risultato ----------------------------------------
    @staticmethod
    def _result_to_utterances(result) -> list[Utterance]:
        """Converte un Result di transcribe.cpp in Utterance del progetto."""
        utterances: list[Utterance] = []

        words = [
            Word(
                start=w.t0_ms / 1000.0,
                end=w.t1_ms / 1000.0,
                text=str(w.text),
            )
            for w in (getattr(result, "words", None) or [])
            if str(w.text).strip()
        ]

        for seg in getattr(result, "segments", None) or []:
            text = str(seg.text).strip()
            if not text:
                continue
            seg_words = words[seg.first_word : seg.first_word + seg.n_words]
            utterances.append(
                Utterance(
                    start=seg.t0_ms / 1000.0,
                    end=seg.t1_ms / 1000.0,
                    text=text,
                    words=seg_words,
                )
            )

        if utterances:
            return utterances

        # Nessun segmento: usa le parole se disponibili, altrimenti il testo
        if words:
            utterances.append(
                Utterance(
                    start=words[0].start,
                    end=words[-1].end,
                    text=" ".join(w.text for w in words).strip(),
                    words=words,
                )
            )
            return utterances

        text = str(getattr(result, "text", "") or "").strip()
        if text:
            utterances.append(Utterance(start=0.0, end=0.0, text=text, words=[]))
        return utterances


def _fmt_hms(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
