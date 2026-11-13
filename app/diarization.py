"""diarization.py - Distinzione dei parlanti (WeSpeaker ONNX, sempre offline).

Backend incluso: "lite" -> Silero VAD + embedding WeSpeaker ONNX + clustering
agglomerativo. Usa solo modelli aperti (Apache-2.0) e funziona senza rete;
la spunta "Attiva distinzione parlanti" nella UI lo attiva su richiesta.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import applog, portable

ProgressFn = Callable[[float, str], None]

WESPEAKER_ONNX = "wespeaker-voxceleb-resnet34-LM.onnx"


class DiarizationError(RuntimeError):
    pass


@dataclass
class Turn:
    start: float
    end: float
    speaker: str


# ---------------------------------------------------------------------------
# Disponibilita' del modello
# ---------------------------------------------------------------------------

def embedding_path() -> Path:
    return portable.EMBEDDING_DIR / WESPEAKER_ONNX


def available() -> bool:
    """True se il modello di embedding WeSpeaker e' presente nel pacchetto."""
    return embedding_path().exists()


def unavailable_reason() -> str:
    return (
        "Modello di embedding WeSpeaker non presente in models/embeddings "
        f"({WESPEAKER_ONNX}). Il pacchetto non e' completo."
    )


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class Diarizer:
    """Diarizzazione semplificata ma interamente offline e senza modelli gated."""

    def __init__(self, threshold: float = 0.60) -> None:
        self.threshold = float(threshold)
        self._embedding = None

    def _load(self):
        if self._embedding is not None:
            return self._embedding

        from .embedding import SpeakerEmbedding

        onnx = embedding_path()
        if not onnx.exists():
            raise DiarizationError(unavailable_reason())
        self._embedding = SpeakerEmbedding(onnx)
        applog.get().info("Modello embedding WeSpeaker caricato")
        return self._embedding

    def diarize(
        self,
        audio_path: Path,
        num_speakers: int = 0,
        cancel: Optional[threading.Event] = None,
        on_progress: Optional[ProgressFn] = None,
    ) -> list[Turn]:
        embedding = self._load()

        if on_progress:
            on_progress(0.05, "Lettura audio per la diarizzazione")

        samples = _read_audio_mono(audio_path, embedding.sample_rate)
        if samples.size == 0:
            return []

        if on_progress:
            on_progress(0.15, "Rilevamento dei tratti vocali (VAD)")

        from .silero_vad import VadOptions, get_speech_timestamps

        speech = get_speech_timestamps(
            samples,
            VadOptions(min_silence_duration_ms=500, speech_pad_ms=200),
            sampling_rate=embedding.sample_rate,
        )
        if not speech:
            return []

        windows, bounds = _build_windows(
            samples, speech, embedding.sample_rate, window_s=1.5
        )
        if not windows:
            return []

        if on_progress:
            on_progress(0.3, f"Estrazione embedding ({len(windows)} finestre)")

        embeddings = _extract_embeddings(embedding, windows, cancel, on_progress)

        if on_progress:
            on_progress(0.8, "Raggruppamento dei parlanti")

        labels = _cluster(embeddings, num_speakers, self.threshold)
        labels = _smooth_labels(labels, passes=2)

        turns: list[Turn] = []
        for (start, end), label in zip(bounds, labels):
            turns.append(Turn(start, end, f"SPEAKER_{int(label):02d}"))
        return _merge_adjacent_turns(turns, gap=0.4)


def _read_audio_mono(path: Path, sample_rate: int):
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != sample_rate:
        duration = data.shape[0] / float(sr)
        target = int(round(duration * sample_rate))
        if target > 0:
            x_old = np.linspace(0.0, duration, num=data.shape[0], endpoint=False)
            x_new = np.linspace(0.0, duration, num=target, endpoint=False)
            data = np.interp(x_new, x_old, data).astype("float32")
    return data


def _build_windows(samples, speech: list[dict], sample_rate: int, window_s: float):
    """Divide ogni tratto vocale in segmenti NON sovrapposti di ~window_s."""
    import numpy as np

    win = int(window_s * sample_rate)
    windows: list[np.ndarray] = []
    bounds: list[tuple[float, float]] = []

    for chunk in speech:
        start = int(chunk["start"])
        end = int(chunk["end"])
        pos = start
        while pos < end:
            seg_start = pos
            seg_end = min(pos + win, end)
            segment = np.zeros(win, dtype="float32")
            chunk_audio = samples[seg_start:seg_end]
            segment[: chunk_audio.shape[0]] = chunk_audio
            windows.append(segment)
            bounds.append((seg_start / sample_rate, seg_end / sample_rate))
            pos = seg_end
    return windows, bounds


def _extract_embeddings(embedding, windows, cancel, on_progress, batch_size: int = 16):
    import numpy as np

    total = len(windows)
    result: list[np.ndarray] = []
    for index in range(0, total, batch_size):
        if cancel is not None and cancel.is_set():
            raise InterruptedError("Diarizzazione annullata")
        batch = np.stack(windows[index : index + batch_size]).astype("float32")
        result.append(np.asarray(embedding(batch)))
        if on_progress and total:
            on_progress(0.3 + 0.5 * min(1.0, (index + batch_size) / total),
                        f"Embedding {min(index + batch_size, total)}/{total}")
    return np.concatenate(result, axis=0) if result else np.zeros((0, 0))


def _kmeans_cosine(embeddings, k: int, n_init: int = 10, max_iter: int = 100):
    """k-means con distanza coseno (vettori gia' normalizzati), inizializzazione k-means++."""
    import numpy as np

    n = embeddings.shape[0]
    k = max(1, min(int(k), n))
    rng = np.random.default_rng(0)

    best_labels = np.zeros(n, dtype=int)
    best_inertia = float("inf")

    for _ in range(n_init):
        centers = [embeddings[int(rng.integers(n))]]
        for _c in range(1, k):
            distance = np.min(1.0 - embeddings @ np.array(centers).T, axis=1)
            distance = np.maximum(distance, 1e-12)
            centers.append(embeddings[int(rng.choice(n, p=distance / distance.sum()))])
        centroids = np.array(centers, dtype=np.float64)

        labels = np.zeros(n, dtype=int)
        for iteration in range(max_iter):
            new_labels = np.argmax(embeddings @ centroids.T, axis=1)
            if iteration and np.array_equal(new_labels, labels):
                break
            labels = new_labels
            for cluster in range(k):
                mask = labels == cluster
                if not mask.any():
                    centroids[cluster] = embeddings[int(rng.integers(n))]
                    continue
                centroid = embeddings[mask].mean(axis=0)
                norm = float(np.linalg.norm(centroid))
                centroids[cluster] = centroid / norm if norm > 0 else centroid

        inertia = float(np.sum(1.0 - np.max(embeddings @ centroids.T, axis=1)))
        if inertia < best_inertia:
            best_inertia = inertia
            best_labels = labels.copy()

    return best_labels


def _silhouette_cosine(embeddings, labels) -> float:
    """Silhouette score medio con distanza coseno."""
    import numpy as np

    unique = np.unique(labels)
    if unique.size < 2:
        return -1.0

    distances = 1.0 - embeddings @ embeddings.T
    scores = []
    for i in range(embeddings.shape[0]):
        own = labels == labels[i]
        own[i] = False
        if not own.any():
            scores.append(0.0)
            continue
        a = float(distances[i, own].mean())
        b = float(
            min(
                distances[i, labels == other].mean()
                for other in unique
                if other != labels[i] and (labels == other).any()
            )
        )
        denominator = max(a, b)
        scores.append((b - a) / denominator if denominator > 0 else 0.0)

    return float(np.mean(scores))


def _cluster(embeddings, num_speakers: int, threshold: float):
    """Clustering sferico (k-means con distanza coseno).

    Se il numero di parlanti e' noto lo si usa direttamente; altrimenti si
    scegle il numero di cluster che massimizza il silhouette score, con
    almeno 2 finestre per cluster.
    """
    import numpy as np

    embeddings = np.asarray(embeddings, dtype="float64")
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = embeddings / norms

    n = normalized.shape[0]
    if n <= 1:
        return np.zeros(n, dtype=int)

    if num_speakers and num_speakers > 0:
        return _kmeans_cosine(normalized, min(int(num_speakers), n))

    max_k = min(6, n)
    best_k = 1
    best_score = -1.0
    for k in range(2, max_k + 1):
        labels = _kmeans_cosine(normalized, k)
        if np.unique(labels).size < 2:
            continue
        sizes = np.bincount(labels)
        if sizes.min() < 2:
            continue
        score = _silhouette_cosine(normalized, labels)
        if score > best_score:
            best_score = score
            best_k = k

    if best_k <= 1 or best_score < 0.10:
        return np.zeros(n, dtype=int)
    return _kmeans_cosine(normalized, best_k)


def _smooth_labels(labels, passes: int = 2):
    """Rimuove le etichette isolate (un solo frame diverso dai vicini).

    A differenza di un filtro di maggioranza non cancella i parlanti con
    pochi frame consecutivi.
    """
    import numpy as np

    labels = np.asarray(labels).copy()
    if labels.size < 3:
        return labels
    for _ in range(passes):
        for i in range(1, labels.size - 1):
            if labels[i - 1] == labels[i + 1] != labels[i]:
                labels[i] = labels[i - 1]
    return labels


def _merge_adjacent_turns(turns: list[Turn], gap: float = 0.4) -> list[Turn]:
    if not turns:
        return []
    turns = sorted(turns, key=lambda t: t.start)
    merged: list[Turn] = [Turn(turns[0].start, turns[0].end, turns[0].speaker)]
    for turn in turns[1:]:
        last = merged[-1]
        if turn.speaker == last.speaker and turn.start - last.end <= gap:
            last.end = max(last.end, turn.end)
        else:
            merged.append(Turn(turn.start, turn.end, turn.speaker))
    return merged
