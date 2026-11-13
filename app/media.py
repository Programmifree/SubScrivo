"""media.py - Estrazione audio/FFmpeg, interamente locale."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from . import applog, portable

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)")

# FFmpeg and ffprobe are separate processes, so the Python socket guard does
# not apply to them. Permit only local files and the pipe used for progress.
# La whitelist e' una difesa in profondita': se su qualche macchina causa un
# blocco o un errore, si riprova senza (il network guard Python resta attivo).
_LOCAL_PROTOCOLS = "file,pipe"

# Timeout di sicurezza per probe/ffprobe: se il processo si blocca (input
# anomalo) non dobbiamo lasciare il thread di lavoro appeso per sempre.
_PROBE_TIMEOUT_S = 60.0

# Secondi di assenza totale di output da FFmpeg prima di considerarlo in
# stallo e terminarlo (poi si ritenta senza whitelist).
_EXTRACT_STALL_S = 180.0

# Messaggio unico per i file privi di traccia audio (caso tipico: video
# scaricati come sola traccia video). Meglio dirlo chiaramente invece del
# generico "FFmpeg non e' riuscito a leggere il file".
_NO_AUDIO_MESSAGE = (
    "Il file non contiene una traccia audio, quindi non c'e' nulla da "
    "trascrivere. I video scaricati come sola traccia video (senza audio) "
    "non sono elaborabili: usa un file che contenga anche l'audio."
)

# Evita la comparsa di finestre console su Windows
_NO_WINDOW = 0
if sys.platform.startswith("win"):
    _NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


class MediaError(RuntimeError):
    pass


def ffmpeg_path() -> str:
    if portable.FFMPEG_EXE.exists():
        return str(portable.FFMPEG_EXE)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise MediaError(
        "FFmpeg non trovato. Verifica che ffmpeg/bin/ffmpeg.exe sia presente "
        "nella cartella del programma."
    )


def ffprobe_path() -> Optional[str]:
    if portable.FFPROBE_EXE.exists():
        return str(portable.FFPROBE_EXE)
    return shutil.which("ffprobe")


def _run(cmd: list[str], timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=_NO_WINDOW,
    )


def probe_duration(path: Path) -> float:
    """Durata in secondi del file audio/video (0.0 se non determinabile).

    Prima con la whitelist dei protocolli, poi (se non risponde o fallisce)
    senza: e' il comportamento delle versioni precedenti, che e' sempre
    funzionato. I processi hanno un timeout: mai attese infinite.
    """
    probe = ffprobe_path()
    if probe:
        for whitelist in (_LOCAL_PROTOCOLS, None):
            cmd = [probe, "-v", "error"]
            if whitelist:
                cmd += ["-protocol_whitelist", whitelist]
            cmd += [
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ]
            try:
                result = _run(cmd, timeout=_PROBE_TIMEOUT_S)
            except Exception:
                continue
            if result.returncode == 0:
                value = result.stdout.strip().splitlines()
                if value:
                    try:
                        return float(value[0])
                    except ValueError:
                        pass

    # Fallback: interroga ffmpeg (prima con whitelist, poi senza)
    for whitelist in (_LOCAL_PROTOCOLS, None):
        cmd = [ffmpeg_path(), "-hide_banner"]
        if whitelist:
            cmd += ["-protocol_whitelist", whitelist]
        cmd += ["-i", str(path)]
        try:
            result = _run(cmd, timeout=_PROBE_TIMEOUT_S)
        except Exception:
            continue
        match = _DURATION_RE.search(result.stderr or "")
        if match:
            h, m, s = match.groups()
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def has_audio_stream(path: Path) -> Optional[bool]:
    """True/False se il file contiene una traccia audio.

    Ritorna None quando il controllo non e' possibile (ffprobe assente o
    errore): in quel caso si procede comunque con l'estrazione, cosi' il
    controllo non puo' bloccare file validi.
    """
    probe = ffprobe_path()
    if not probe:
        return None

    for whitelist in (_LOCAL_PROTOCOLS, None):
        cmd = [probe, "-v", "error"]
        if whitelist:
            cmd += ["-protocol_whitelist", whitelist]
        cmd += [
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(path),
        ]
        try:
            result = _run(cmd, timeout=_PROBE_TIMEOUT_S)
        except Exception:
            continue
        if result.returncode == 0:
            # Con -select_streams a: output vuoto = nessuna traccia audio.
            return bool((result.stdout or "").strip())
    return None


def extract_audio(
    src: Path,
    dst: Path,
    cancel: Optional[threading.Event] = None,
    on_progress: Optional[Callable[[float], None]] = None,
    duration: float = 0.0,
) -> Path:
    """Estrae l'audio in WAV PCM 16 kHz mono con FFmpeg locale.

    Usa `-progress pipe:1` per riportare l'avanzamento. Supporta
    l'annullamento terminando il processo FFmpeg.

    Se FFmpeg resta in stallo (nessun output per _EXTRACT_STALL_S secondi)
    viene terminato e l'estrazione ritenta senza la whitelist dei protocolli,
    che e' il comportamento delle versioni precedenti. Cosi' la protezione
    extra non puo' mai lasciare il lavoro appeso per sempre.
    """
    ffmpeg = ffmpeg_path()
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Controllo preventivo: un video senza traccia audio non produce alcun
    # WAV e FFmpeg fallirebbe con un messaggio poco chiaro. Se ffprobe non e'
    # disponibile (None) si prosegue: l'estrazione dira' l'ultima parola.
    if has_audio_stream(src) is False:
        applog.get().warning(
            "Nessuna traccia audio rilevata in '%s': estrazione impossibile",
            src.name,
        )
        raise MediaError(_NO_AUDIO_MESSAGE)

    for whitelist in (_LOCAL_PROTOCOLS, None):
        try:
            return _extract_audio_once(
                ffmpeg, src, dst, whitelist, cancel, on_progress, duration
            )
        except _Stalled:
            applog.get().warning(
                "FFmpeg in stallo durante l'estrazione; ritento senza "
                "whitelist dei protocolli"
            )
            try:
                dst.unlink()
            except Exception:
                pass
            if whitelist is None:
                raise MediaError(
                    "FFmpeg non risponde: estrazione interrotta dopo "
                    f"{_EXTRACT_STALL_S:.0f} s di silenzio"
                )
        except InterruptedError:
            raise
    raise MediaError("Estrazione audio non riuscita.")  # non raggiunto


class _Stalled(RuntimeError):
    """FFmpeg non ha prodotto output entro il tempo di stallo."""


def _extract_audio_once(
    ffmpeg: str,
    src: Path,
    dst: Path,
    whitelist: Optional[str],
    cancel: Optional[threading.Event],
    on_progress: Optional[Callable[[float], None]],
    duration: float,
) -> Path:
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
    ]
    if whitelist:
        cmd += ["-protocol_whitelist", whitelist]
    cmd += [
        "-i",
        str(src),
        "-vn",
        "-sn",
        "-dn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-map_metadata",
        "-1",
        "-progress",
        "pipe:1",
        "-nostats",
        "-y",
        str(dst),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_NO_WINDOW,
    )

    assert proc.stdout is not None
    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        try:
            if proc.stderr is not None:
                stderr_chunks.append(proc.stderr.read())
        except Exception:
            pass

    drain = threading.Thread(target=_drain_stderr, daemon=True)
    drain.start()

    stalled = threading.Event()

    # Ultimo momento in cui FFmpeg ha prodotto output; lista mutabile cosi'
    # il thread watchdog vede sempre il valore aggiornato.
    last_activity = [time.monotonic()]

    def _watchdog() -> None:
        # Termina FFmpeg se non fa nulla per _EXTRACT_STALL_S secondi.
        while not stalled.is_set():
            if proc.poll() is not None:
                return
            if cancel is not None and cancel.is_set():
                return  # il loop principale gestisce l'annullamento
            time.sleep(1.0)
            if proc.poll() is not None:
                return
            if time.monotonic() - last_activity[0] > _EXTRACT_STALL_S:
                stalled.set()
                try:
                    proc.kill()
                except Exception:
                    pass

    watchdog = threading.Thread(target=_watchdog, daemon=True)
    watchdog.start()

    try:
        for line in proc.stdout:
            last_activity[0] = time.monotonic()
            if cancel is not None and cancel.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                raise InterruptedError("Estrazione audio annullata")

            if on_progress and line.startswith("out_time_us=") and duration > 0:
                try:
                    micros = int(line.split("=", 1)[1].strip())
                    on_progress(min(1.0, (micros / 1_000_000) / duration))
                except Exception:
                    pass
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass

    stderr = "".join(stderr_chunks)
    returncode = proc.wait()
    drain.join(timeout=5)
    if stalled.is_set():
        raise _Stalled()
    if returncode != 0:
        detail = (stderr or "").strip()
        if "does not contain any stream" in detail.lower():
            # Caso tipico: file video privo di traccia audio.
            raise MediaError(_NO_AUDIO_MESSAGE)
        raise MediaError(
            "FFmpeg non e' riuscito a leggere il file di input. "
            f"Dettaglio: {detail[:500]}"
        )
    if not dst.exists() or dst.stat().st_size == 0:
        raise MediaError(
            "FFmpeg non ha prodotto alcun audio utilizzabile. Verifica che il "
            "file contenga una traccia audio."
        )
    return dst


def guess_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".wmv", ".flv"}:
        return "video"
    return "audio"