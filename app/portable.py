"""
portable.py - Ambiente portabile, percorsi e protezione offline.

Questo modulo DEVE essere importato per primo (prima di onnxruntime,
soundfile, ecc.) perche' imposta tutte le variabili d'ambiente che
impediscono scritture fuori dalla cartella portabile e qualsiasi accesso
alla rete.

Obiettivi:
  * nessuna scrittura in AppData / profilo utente / cache di sistema;
  * nessun accesso Internet (HuggingFace offline, proxy volutamente rotto,
    network guard opzionale che blocca le connessioni non-loopback);
  * nessuna telemetria;
  * percorsi dei modelli sempre locali.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Individuazione della radice portabile
# ---------------------------------------------------------------------------

MARKER_NAME = "portable.ini"


def _find_root() -> Path:
    # 1) Override esplicito (utile in sviluppo/test)
    env = os.environ.get("SUBSCRIVO_HOME")
    if env:
        return Path(env).expanduser().resolve()

    # 2) Eseguibile congelato (PyInstaller o simile)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    # 3) Risale dall'app/ cercando il marker portable.ini
    here = Path(__file__).resolve().parent
    for candidate in (here.parent, here, here.parent.parent):
        if (candidate / MARKER_NAME).exists():
            return candidate

    # 4) Fallback: cartella che contiene app/
    return here.parent


ROOT = _find_root()

# Sottocartelle della radice portabile
APP_DIR = ROOT / "app"
WORK_DIR = ROOT / "work"
TEMP_DIR = WORK_DIR / "temp"
CACHE_DIR = WORK_DIR / "cache"
LOG_DIR = WORK_DIR / "logs"
CONFIG_DIR = WORK_DIR / "config"
MODELS_DIR = ROOT / "models"
# Modello ASR incluso nel pacchetto (runtime transcribe.cpp / ggml)
GGUF_MODELS_DIR = MODELS_DIR / "gguf"
# Modello di embedding per la distinzione dei parlanti (WeSpeaker ONNX)
EMBEDDING_DIR = MODELS_DIR / "embeddings"
# Cache delle librerie, sempre dentro la cartella portabile
HF_DIR = CACHE_DIR / "huggingface"
# Libreria nativa transcribe.dll + DLL ggml
NATIVE_DIR = ROOT / "native"
FFMPEG_BIN = ROOT / "ffmpeg" / "bin"
FFMPEG_EXE = FFMPEG_BIN / "ffmpeg.exe"
FFPROBE_EXE = FFMPEG_BIN / "ffprobe.exe"

# Nome dei file sentinella / lock
RUN_MARKER = TEMP_DIR / ".running"
LOCK_FILE = WORK_DIR / ".lock"

# Versione del pacchetto (mostrata nella UI)
VERSION = "1.0.0"


def _ensure_dirs() -> None:
    for d in (
        WORK_DIR,
        TEMP_DIR,
        CACHE_DIR,
        LOG_DIR,
        CONFIG_DIR,
        MODELS_DIR,
        EMBEDDING_DIR,
        GGUF_MODELS_DIR,
        HF_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


# ---------------------------------------------------------------------------
# Variabili d'ambiente: cache locali + offline
# ---------------------------------------------------------------------------

def setup_environment() -> None:
    """Imposta le variabili d'ambiente per un funzionamento 100% portabile."""
    temp = str(TEMP_DIR)
    cache = str(CACHE_DIR)
    hf = str(HF_DIR)

    # --- File temporanei solo nella cartella portabile ---
    os.environ["TMP"] = temp
    os.environ["TEMP"] = temp
    os.environ["TMPDIR"] = temp

    # --- Cache delle librerie solo nella cartella portabile ---
    os.environ["HF_HOME"] = hf
    os.environ["HF_HUB_CACHE"] = str(HF_DIR / "hub")
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(HF_DIR / "hub")
    os.environ["XDG_CACHE_HOME"] = cache
    os.environ["MPLCONFIGDIR"] = str(CACHE_DIR / "matplotlib")
    os.environ["NUMBA_CACHE_DIR"] = str(CACHE_DIR / "numba")
    os.environ["PYTHONPYCACHEPREFIX"] = str(CACHE_DIR / "pycache")

    # --- Offline rigoroso ---
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    # Proxy volutamente non valido: qualsiasi tentativo HTTP fallisce subito
    # (difesa in profondita' oltre a HF_HUB_OFFLINE).
    if os.environ.get("SUBSCRIVO_STRICT_OFFLINE", "1") != "0":
        os.environ.setdefault("HTTP_PROXY", "http://127.0.0.1:9")
        os.environ.setdefault("HTTPS_PROXY", "http://127.0.0.1:9")
        os.environ.setdefault("ALL_PROXY", "socks5://127.0.0.1:9")
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")

    # --- Python: niente pycache nel profilo, niente site utente ---
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PYTHONUTF8"] = "1"

    # --- Evita il crash "libiomp5md.dll already initialized" su Windows ---
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

    # --- FFmpeg locale nel PATH ---
    if FFMPEG_BIN.exists():
        os.environ["PATH"] = str(FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")


# ---------------------------------------------------------------------------
# Network guard: impedisce connessioni di rete non-loopback
# ---------------------------------------------------------------------------

_NETWORK_GUARD_INSTALLED = False


class OfflineViolation(RuntimeError):
    pass


def install_network_guard() -> None:
    """Blocca ogni connessione TCP/UDP verso indirizzi non locali.

    E' una rete di sicurezza: anche se una libreria tentasse un download,
    la connessione viene rifiutata con un errore esplicito invece di
    contattare Internet. Le connessioni loopback restano permesse perche'
    alcune librerie (multiprocessing, IPC) le usano.
    """
    global _NETWORK_GUARD_INSTALLED
    if _NETWORK_GUARD_INSTALLED or os.environ.get("SUBSCRIVO_NETWORK_GUARD", "1") == "0":
        return

    import socket

    _real_connect = socket.socket.connect
    _real_connect_ex = socket.socket.connect_ex
    _real_sendto = socket.socket.sendto

    def _is_local(address) -> bool:
        try:
            if isinstance(address, tuple):
                host = address[0]
            else:
                host = str(address)
            if host in ("localhost", "", "::1", "0.0.0.0"):
                return True
            import ipaddress

            ip = ipaddress.ip_address(host)
            return ip.is_loopback or ip.is_unspecified
        except Exception:
            return False

    def _guard_connect(self, address):  # noqa: ANN001
        if not _is_local(address):
            raise OfflineViolation(
                f"Connessione di rete bloccata (modalita' offline): {address!r}"
            )
        return _real_connect(self, address)

    def _guard_connect_ex(self, address):  # noqa: ANN001
        if not _is_local(address):
            raise OfflineViolation(
                f"Connessione di rete bloccata (modalita' offline): {address!r}"
            )
        return _real_connect_ex(self, address)

    def _guard_sendto(self, data, *args):  # noqa: ANN001
        address = args[-1] if args else None
        if address is not None and not _is_local(address):
            raise OfflineViolation(
                f"Invio di rete bloccato (modalita' offline): {address!r}"
            )
        return _real_sendto(self, data, *args)

    socket.socket.connect = _guard_connect
    socket.socket.connect_ex = _guard_connect_ex
    socket.socket.sendto = _guard_sendto
    _NETWORK_GUARD_INSTALLED = True


# ---------------------------------------------------------------------------
# Pulizia dei file temporanei
# ---------------------------------------------------------------------------

def cleanup_temp(aggressive: bool = True) -> list[str]:
    """Elimina i file temporanei nella cartella work/temp.

    Ritorna la lista di elementi rimossi. Non tocca il sentinel .running
    (la sua gestione e' separata).
    """
    removed: list[str] = []
    if not TEMP_DIR.exists():
        return removed

    for item in TEMP_DIR.iterdir():
        if item.name == ".running":
            continue
        try:
            if item.is_dir():
                import shutil

                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink()
            removed.append(item.name)
        except Exception:
            pass
    return removed


def mark_running() -> None:
    """Scrive il sentinel di esecuzione (rileva interruzioni impreviste)."""
    from datetime import datetime

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    RUN_MARKER.write_text(
        f"pid={os.getpid()}\nstarted={datetime.now().isoformat()}\n",
        encoding="utf-8",
    )


def clear_running() -> None:
    try:
        if RUN_MARKER.exists():
            RUN_MARKER.unlink()
    except Exception:
        pass


def claimed_crash() -> bool:
    """True se alla partenza e' stato trovato un sentinel di run precedente."""
    return RUN_MARKER.exists()


def startup_cleanup() -> bool:
    """Pulizia all'avvio. Ritorna True se ha rilevato un'interruzione."""
    crash = claimed_crash()
    cleanup_temp()
    clear_running()
    return crash