"""engine.py - Orchestrazione: estrazione audio -> trascrizione -> diarizzazione."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import applog, diarization, media, merge, portable
from .transcription import MODEL_FILENAME, Utterance, create_transcriber

# Callback di avanzamento: (frazione 0..1, fase, dettaglio)
ProgressCB = Callable[[float, str, str], None]


@dataclass
class JobOptions:
    model_name: str = MODEL_FILENAME
    language: str = "auto"
    # True = distinzione parlanti con WeSpeaker (offline)
    diarize: bool = False
    # "cpu" | "auto" (Vulkan se disponibile) per il runtime ggml
    asr_backend: str = "cpu"
    num_speakers: int = 1
    merge_gap_s: float = 1.0
    cluster_threshold: float = 0.60
    cpu_threads: int = 0
    delete_temp: bool = True


@dataclass
class JobResult:
    source_name: str
    duration: float
    language: str
    model: str
    backend: str
    speakers: list[str] = field(default_factory=list)
    segments: list[dict] = field(default_factory=list)
    paragraphs: list[dict] = field(default_factory=list)


class EngineError(RuntimeError):
    pass


def _mapped(progress: Optional[ProgressCB], stage: str, frac: float, detail: str) -> None:
    if progress:
        progress(max(0.0, min(1.0, frac)), stage, detail)


def run_job(
    input_path: Path,
    options: JobOptions,
    cancel: Optional[threading.Event] = None,
    on_progress: Optional[ProgressCB] = None,
) -> JobResult:
    cancel = cancel or threading.Event()
    input_path = Path(input_path)
    if not input_path.exists():
        raise EngineError(f"File di input non trovato: {input_path.name}")

    started = time.time()
    applog.get().info(
        "Avvio lavoro: tipo=%s, modello=%s, diarizzazione=%s",
        media.guess_kind(input_path),
        options.model_name,
        "on" if options.diarize else "off",
    )

    duration = 0.0
    audio_path: Optional[Path] = None
    result: Optional[JobResult] = None

    try:
        # --- 1. Sonda durata ---
        _mapped(on_progress, "Analisi file", 0.01, "Lettura informazioni del file")
        duration = media.probe_duration(input_path)
        applog.get().info(
            "Analisi file completata: durata=%.1f s, tipo=%s",
            duration,
            media.guess_kind(input_path),
        )
        if cancel.is_set():
            raise InterruptedError("Operazione annullata")

        # --- 2. Estrazione audio ---
        _mapped(on_progress, "Estrazione audio", 0.03, "Conversione in WAV 16 kHz mono")
        audio_path = portable.TEMP_DIR / f"audio_{time.time_ns()}.wav"

        def _extract_progress(fraction: float) -> None:
            _mapped(
                on_progress,
                "Estrazione audio",
                0.03 + 0.05 * fraction,
                f"Estrazione audio {int(fraction * 100)}%",
            )

        media.extract_audio(
            input_path, audio_path, cancel=cancel, on_progress=_extract_progress, duration=duration
        )
        applog.get().info(
            "Estrazione audio completata: %d byte",
            audio_path.stat().st_size,
        )
        if cancel.is_set():
            raise InterruptedError("Operazione annullata")

        # --- 3. Trascrizione (Parakeet Ultra, GGUF) ---
        transcriber = create_transcriber(
            model_name=options.model_name,
            cpu_threads=options.cpu_threads,
            backend=options.asr_backend,
        )

        def _transcribe_progress(fraction: float, detail: str, _seconds: float) -> None:
            _mapped(on_progress, "Trascrizione", 0.08 + 0.50 * fraction, detail)

        utterances, meta = transcriber.transcribe(
            audio_path,
            duration=duration or 0.0,
            language=options.language,
            cancel=cancel,
            on_progress=_transcribe_progress,
        )
        if not duration:
            duration = meta.get("duration", 0.0)
        if cancel.is_set():
            raise InterruptedError("Operazione annullata")

        # --- 4. Diarizzazione (opzionale) ---
        turns: list = []
        if not options.diarize:
            resolved_backend = "off"
            _mapped(on_progress, "Diarizzazione", 0.58, "Diarizzazione disattivata")
            applog.get().info("Diarizzazione: OFF")
        else:
            if not diarization.available():
                raise EngineError(diarization.unavailable_reason())
            resolved_backend = "lite"

            _mapped(on_progress, "Diarizzazione", 0.58, "Backend: WeSpeaker (offline)")

            def _diarize_progress(fraction: float, detail: str) -> None:
                _mapped(on_progress, "Diarizzazione", 0.58 + 0.32 * fraction, detail)

            diarizer = diarization.Diarizer(threshold=options.cluster_threshold)
            turns = diarizer.diarize(
                audio_path,
                num_speakers=options.num_speakers,
                cancel=cancel,
                on_progress=_diarize_progress,
            )
            if cancel.is_set():
                raise InterruptedError("Operazione annullata")

        # --- 5. Fusione ---
        _mapped(on_progress, "Combinazione", 0.90, "Associazione parlanti/frasi")
        merged = merge.assign_speakers(utterances, turns)
        if resolved_backend == "off":
            speakers: list[str] = []
        else:
            speakers = merge.relabel_speakers(merged)
        grouped = merge.group_segments(merged, gap=options.merge_gap_s)

        result = JobResult(
            source_name=input_path.name,
            duration=float(duration or 0.0),
            language=str(meta.get("language", "unknown")),
            model=options.model_name,
            backend=resolved_backend,
            speakers=speakers,
            segments=[_segment_dict(u) for u in merged],
            paragraphs=[_segment_dict(u) for u in grouped],
        )

        _mapped(on_progress, "Completato", 1.0, "Elaborazione completata")
        applog.get().info(
            "Lavoro completato in %.1f s (%d segmenti, %d parlanti)",
            time.time() - started,
            len(result.segments),
            len(result.speakers),
        )
        return result

    except InterruptedError:
        applog.get().info("Lavoro annullato dall'utente")
        raise
    except Exception as exc:  # noqa: BLE001
        applog.log_error("Errore durante l'elaborazione", exc)
        raise
    finally:
        if audio_path is not None and options.delete_temp:
            _delete_temp_file(audio_path)


def _delete_temp_file(path: Path, max_retries: int = 5, delay: float = 0.2) -> None:
    """Elimina un file temporaneo, ritentando se e' ancora bloccato dal sistema."""
    for attempt in range(max_retries):
        try:
            path.unlink(missing_ok=True)
            return
        except Exception as exc:
            if attempt == max_retries - 1:
                applog.log_error("Impossibile eliminare il file temporaneo", exc)
            else:
                time.sleep(delay)


def _segment_dict(utterance: Utterance) -> dict:
    d = {
        "start": float(utterance.start),
        "end": float(utterance.end),
        "speaker": utterance.speaker,
        "text": utterance.text,
    }
    if getattr(utterance, "words", None):
        d["words"] = [
            {"start": float(w.start), "end": float(w.end), "text": str(w.text)}
            for w in utterance.words
        ]
    return d
