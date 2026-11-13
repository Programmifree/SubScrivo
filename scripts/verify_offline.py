"""verify_offline.py - Verifica le garanzie offline e la localizzazione dei dati.

Uso:
    python\python.exe scripts\verify_offline.py
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import portable  # noqa: E402


def _verify_ffmpeg_protocols(failures: list[str]) -> None:
    """Verify both bundled tools reject network URLs but read local media."""
    sample = REPO_ROOT / "samples" / "esempio_1_parlante.wav"
    tools = (
        ("ffprobe", portable.FFPROBE_EXE),
        ("ffmpeg", portable.FFMPEG_EXE),
    )
    url = "http://127.0.0.1:9/offline-probe"

    for name, executable in tools:
        if not executable.is_file():
            failures.append(f"{name} locale non trovato: {executable}")
            continue

        if name == "ffprobe":
            local_args = [
                "-v", "error", "-protocol_whitelist", "file,pipe",
                "-show_entries", "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", str(sample),
            ]
            remote_args = [
                "-v", "error", "-protocol_whitelist", "file,pipe",
                "-show_entries", "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", url,
            ]
        else:
            local_args = [
                "-hide_banner", "-v", "error", "-protocol_whitelist",
                "file,pipe", "-i", str(sample), "-f", "null", "-",
            ]
            remote_args = [
                "-hide_banner", "-v", "error", "-protocol_whitelist",
                "file,pipe", "-i", url, "-f", "null", "-",
            ]

        try:
            local = subprocess.run(
                [str(executable), *local_args], capture_output=True, text=True,
                timeout=30, check=False,
            )
            if local.returncode != 0:
                failures.append(f"{name} non riesce a leggere il file locale di prova")
            else:
                print(f"OK  {name}: file locale consentito")

            remote = subprocess.run(
                [str(executable), *remote_args], capture_output=True, text=True,
                timeout=10, check=False,
            )
            diagnostic = (remote.stderr or "").lower()
            if "not on whitelist" not in diagnostic:
                failures.append(f"{name} non ha rifiutato il protocollo HTTP")
            else:
                print(f"OK  {name}: HTTP rifiutato dalla whitelist")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Test protocolli {name} non riuscito: {type(exc).__name__}: {exc}")


def main() -> int:
    portable.setup_environment()
    portable.install_network_guard()

    failures: list[str] = []
    print(f"Radice portabile: {portable.ROOT}")
    print(f"TEMP: {portable.TEMP_DIR}")

    # 1. TEMP deve stare dentro la radice portabile
    for var in ("TMP", "TEMP", "TMPDIR"):
        value = os.environ.get(var, "")
        if not value or Path(value).resolve() != portable.TEMP_DIR.resolve():
            failures.append(f"{var} non punta a work/temp ({value!r})")
        else:
            print(f"OK  {var} = {value}")

    # 2. Cache dentro la radice
    for var in ("HF_HOME", "TORCH_HOME", "MPLCONFIGDIR", "PYANNOTE_CACHE", "XDG_CACHE_HOME"):
        value = os.environ.get(var, "")
        try:
            inside = Path(value).resolve().is_relative_to(portable.ROOT)
        except Exception:
            inside = False
        if not inside:
            failures.append(f"{var} fuori dalla radice ({value!r})")
        else:
            print(f"OK  {var} = {value}")

    # 3. Modalita' offline di HuggingFace
    for var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
        if os.environ.get(var) != "1":
            failures.append(f"{var} non impostata a 1")
        else:
            print(f"OK  {var}=1")

    # 4. Verifica il guard senza DNS e senza tentare traffico esterno.
    # L'oggetto fittizio garantisce che, se il guard manca, il socket nativo
    # fallisca prima di poter aprire una connessione.
    try:
        socket.socket.connect(object(), ("203.0.113.1", 80))
        failures.append("Il network guard non ha rifiutato una destinazione esterna")
    except portable.OfflineViolation:
        print("OK  network guard: destinazione esterna rifiutata senza traffico")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Network guard non verificabile: {type(exc).__name__}: {exc}")

    # 5. FFmpeg/ffprobe: file locali consentiti, HTTP rifiutato prima della rete.
    _verify_ffmpeg_protocols(failures)

    # 6. Loopback permesso (nessuna OfflineViolation)
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 9))
    except portable.OfflineViolation:
        failures.append("Il loopback e' stato bloccato per errore")
    except Exception:
        print("OK  loopback consentito (nessuna OfflineViolation)")
    finally:
        s.close()

    # 7. Modelli locali
    from app import diarization, transcription

    models = transcription.available_models()
    print(f"Modelli GGUF: {models or 'NESSUNO'}")
    if not transcription.model_available():
        failures.append(
            f"Modello {transcription.MODEL_FILENAME} non presente in models/gguf"
        )
    print(f"WeSpeaker (diarizzazione): {diarization.available()}")

    print()
    if failures:
        print("VERIFICA FALLITA:")
        for item in failures:
            print("  -", item)
        return 1
    print("VERIFICA SUPERATA: dati locali, offline attivo, modelli presenti.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())