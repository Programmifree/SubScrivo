"""settings.py - Configurazione persistente nella cartella portabile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import portable

CONFIG_FILE = portable.CONFIG_DIR / "settings.json"

DEFAULTS: dict[str, Any] = {
    # Lingua: "auto" = rilevata dal modello (Parakeet Ultra e' multilingua)
    "language": "auto",
    # Distinzione parlanti (WeSpeaker ONNX, sempre offline)
    "diarization": False,
    # Backend per il runtime ggml (transcribe.cpp): "cpu" oppure "auto".
    # "cpu" e' il predefinito: funziona sempre e non dipende dai driver.
    # "auto" usa Vulkan se c'e' una GPU compatibile (piu' veloce, ma il
    # modello deve entrare nella memoria video).
    "asr_backend": "cpu",
    # Numero di parlanti: 1 = un solo parlante (default, tipico per webinar);
    # 0 = rilevamento automatico; N = numero noto di parlanti
    "num_speakers": 1,
    # Unisce frasi consecutive dello stesso parlante se il gap < soglia (s)
    "merge_gap_s": 1.0,
    # Soglia di clustering per la distinzione parlanti (distanza coseno)
    "cluster_threshold": 0.60,
    # Thread CPU per il runtime nativo (0 = auto)
    "cpu_threads": 0,
    # Mantieni il network guard attivo
    "network_guard": True,
    # Elimina i WAV temporanei subito dopo l'uso
    "delete_temp_after_job": True,
}


def load() -> dict[str, Any]:
    data = dict(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
    except Exception:
        pass
    return data


def save(data: dict[str, Any]) -> None:
    try:
        portable.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        CONFIG_FILE.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass
