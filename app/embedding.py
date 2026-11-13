"""embedding.py - Embedding vocale WeSpeaker con ONNX Runtime (solo CPU).

La distinzione dei parlanti ha bisogno di un vettore (embedding) per ogni
finestra di voce. Il modello incluso e' `wespeaker-voxceleb-resnet34-LM`
(Apache-2.0) in formato ONNX: accetta feature filterbank Kaldi a 80 canali e
restituisce l'embedding del parlante.

Qui le feature sono calcolate in NumPy (stessa matematica del filterbank Kaldi
a 80 canali usato da WeSpeaker), cosi' non servono PyTorch ne' torchaudio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

SAMPLE_RATE = 16000
NUM_MEL_BINS = 80
FRAME_LENGTH_MS = 25.0
FRAME_SHIFT_MS = 10.0
PREEMPHASIS = 0.97
LOW_FREQ = 20.0
HIGH_FREQ = 0.0  # <= 0 -> offset dal Nyquist
EPSILON = np.finfo(np.float32).eps


# ---------------------------------------------------------------------------
# Filterbank Kaldi (equivalente a torchaudio.compliance.kaldi.fbank)
# ---------------------------------------------------------------------------

def _mel_scale(freq: np.ndarray) -> np.ndarray:
    return 1127.0 * np.log(1.0 + freq / 700.0)


def _inverse_mel_scale(mel_freq: np.ndarray) -> np.ndarray:
    return 700.0 * (np.exp(mel_freq / 1127.0) - 1.0)


def _next_power_of_two(value: int) -> int:
    return 1 if value == 0 else 2 ** (value - 1).bit_length()


def _mel_banks(num_bins: int, window_length_padded: int, sample_freq: float) -> np.ndarray:
    """Matrice (num_bins, window_length_padded // 2 + 1) dei filtri triangolari."""
    num_fft_bins = window_length_padded // 2
    nyquist = 0.5 * sample_freq
    high_freq = HIGH_FREQ if HIGH_FREQ > 0.0 else HIGH_FREQ + nyquist

    fft_bin_width = sample_freq / window_length_padded
    mel_low = _mel_scale(np.asarray(LOW_FREQ))
    mel_high = _mel_scale(np.asarray(high_freq))
    delta = (mel_high - mel_low) / (num_bins + 1)

    index = np.arange(num_bins)[:, None]
    left = mel_low + index * delta
    center = mel_low + (index + 1.0) * delta
    right = mel_low + (index + 2.0) * delta

    mel = _mel_scale(fft_bin_width * np.arange(num_fft_bins))[None, :]
    up = (mel - left) / (center - left)
    down = (right - mel) / (right - center)
    banks = np.maximum(0.0, np.minimum(up, down)).astype(np.float32)

    # La colonna del Nyquist resta a zero (come fa Kaldi/torchaudio).
    return np.pad(banks, ((0, 0), (0, 1)), mode="constant", constant_values=0.0)


def compute_fbank(
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    num_mel_bins: int = NUM_MEL_BINS,
) -> np.ndarray:
    """Feature filterbank logaritmiche (frame, num_mel_bins) da audio mono."""
    samples = np.asarray(samples, dtype=np.float64).reshape(-1)
    if samples.size == 0:
        return np.zeros((0, num_mel_bins), dtype=np.float32)

    # I modelli WeSpeaker sono addestrati su campioni int16 (scalati).
    samples = samples * float(1 << 15)

    window_size = int(sample_rate * FRAME_LENGTH_MS / 1000.0)
    window_shift = int(sample_rate * FRAME_SHIFT_MS / 1000.0)
    padded = _next_power_of_two(window_size)
    if samples.size < window_size:
        return np.zeros((0, num_mel_bins), dtype=np.float32)

    num_frames = 1 + (samples.size - window_size) // window_shift
    strided = np.lib.stride_tricks.as_strided(
        samples,
        shape=(num_frames, window_size),
        strides=(samples.strides[0] * window_shift, samples.strides[0]),
    ).copy()

    # Rimozione della componente continua per frame.
    strided -= strided.mean(axis=1, keepdims=True)

    # Pre-enfasi (il primo campione usa se stesso, come il pad "replicate").
    previous = np.empty_like(strided)
    previous[:, 0] = strided[:, 0]
    previous[:, 1:] = strided[:, :-1]
    strided -= PREEMPHASIS * previous

    # Finestra di Hamming (periodic=False, come torchaudio).
    window = 0.54 - 0.46 * np.cos(
        2.0 * np.pi * np.arange(window_size) / (window_size - 1)
    )
    strided *= window[None, :]

    if padded != window_size:
        strided = np.pad(
            strided, ((0, 0), (0, padded - window_size)), mode="constant"
        )

    spectrum = np.abs(np.fft.rfft(strided, n=padded, axis=1)) ** 2.0
    banks = _mel_banks(num_mel_bins, padded, float(sample_rate))
    energies = spectrum @ banks.T
    energies = np.log(np.maximum(energies, EPSILON)).astype(np.float32)

    # Sottrazione della media nel tempo (normalizzazione WeSpeaker).
    return energies - energies.mean(axis=0, keepdims=True)


# ---------------------------------------------------------------------------
# Embedding ONNX
# ---------------------------------------------------------------------------

class SpeakerEmbedding:
    """Calcola l'embedding del parlante per una o piu' finestre audio."""

    sample_rate = SAMPLE_RATE

    def __init__(self, model_path: Path | str) -> None:
        import onnxruntime

        self.model_path = Path(model_path)
        options = onnxruntime.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        options.log_severity_level = 4
        self.session = onnxruntime.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
            sess_options=options,
        )

    def __call__(self, windows: np.ndarray) -> np.ndarray:
        """`windows` ha forma (n, campioni) -> embedding (n, dimensione)."""
        windows = np.asarray(windows, dtype=np.float32)
        if windows.ndim == 1:
            windows = windows[None, :]
        if windows.shape[0] == 0:
            return np.zeros((0, 0), dtype=np.float32)

        features = np.stack([compute_fbank(w) for w in windows], axis=0)
        return self.session.run(
            output_names=["embs"], input_feed={"feats": features}
        )[0]

    @property
    def dimension(self) -> int:
        return int(self.session.get_outputs()[0].shape[-1])


def load(model_path: Optional[Path] = None):
    """Carica il modello incluso (models/embeddings/...)."""
    from . import portable

    path = model_path or (portable.EMBEDDING_DIR / "wespeaker-voxceleb-resnet34-LM.onnx")
    return SpeakerEmbedding(path)
