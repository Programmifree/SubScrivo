"""silero_vad.py - Voice Activity Detection (Silero VAD v5, ONNX, offline).

Implementazione locale derivata dal modulo ``faster_whisper/vad.py``
(faster-whisper, licenza MIT — vedi ``licenses/03-faster-whisper-MIT.txt``).
Usa i due modelli ONNX inclusi in ``native/silero-vad/`` tramite onnxruntime.
Non dipende da PyAV, CTranslate2 ne' da altre parti di faster-whisper.

Espone le stesse strutture usate dal progetto: ``VadOptions`` e
``get_speech_timestamps``.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from . import portable

_ENCODER_FILE = "silero_encoder_v5.onnx"
_DECODER_FILE = "silero_decoder_v5.onnx"


def assets_dir():
    """Cartella che contiene i modelli ONNX del VAD."""
    return portable.NATIVE_DIR / "silero-vad"


@dataclass
class VadOptions:
    threshold: float = 0.5
    neg_threshold: Optional[float] = None
    min_speech_duration_ms: int = 0
    max_speech_duration_s: float = float("inf")
    min_silence_duration_ms: int = 2000
    speech_pad_ms: int = 400


def get_speech_timestamps(
    audio: np.ndarray,
    vad_options: Optional[VadOptions] = None,
    sampling_rate: int = 16000,
) -> List[dict]:
    """Divide l'audio (mono float32) nei tratti in cui c'e' voce.

    Ritorna una lista di dizionari ``{"start": campione, "end": campione}``.
    """
    vad_options = vad_options or VadOptions()

    threshold = vad_options.threshold
    neg_threshold = vad_options.neg_threshold
    min_speech_duration_ms = vad_options.min_speech_duration_ms
    max_speech_duration_s = vad_options.max_speech_duration_s
    min_silence_duration_ms = vad_options.min_silence_duration_ms
    window_size_samples = 512
    speech_pad_ms = vad_options.speech_pad_ms
    min_speech_samples = sampling_rate * min_speech_duration_ms / 1000
    speech_pad_samples = sampling_rate * speech_pad_ms / 1000
    max_speech_samples = (
        sampling_rate * max_speech_duration_s
        - window_size_samples
        - 2 * speech_pad_samples
    )
    min_silence_samples = sampling_rate * min_silence_duration_ms / 1000
    min_silence_samples_at_max_speech = sampling_rate * 98 / 1000

    audio_length_samples = len(audio)

    model = get_vad_model()

    padded_audio = np.pad(
        audio, (0, window_size_samples - audio.shape[0] % window_size_samples)
    )
    speech_probs = model(padded_audio.reshape(1, -1)).squeeze(0)

    triggered = False
    speeches = []
    current_speech = {}
    if neg_threshold is None:
        neg_threshold = max(threshold - 0.15, 0.01)

    # to save potential segment end (and tolerate some silence)
    temp_end = 0
    # to save potential segment limits in case of maximum segment size reached
    prev_end = next_start = 0

    for i, speech_prob in enumerate(speech_probs):
        if (speech_prob >= threshold) and temp_end:
            temp_end = 0
            if next_start < prev_end:
                next_start = window_size_samples * i

        if (speech_prob >= threshold) and not triggered:
            triggered = True
            current_speech["start"] = window_size_samples * i
            continue

        if (
            triggered
            and (window_size_samples * i) - current_speech["start"] > max_speech_samples
        ):
            if prev_end:
                current_speech["end"] = prev_end
                speeches.append(current_speech)
                current_speech = {}
                # previously reached silence (< neg_thres) and is still not speech (< thres)
                if next_start < prev_end:
                    triggered = False
                else:
                    current_speech["start"] = next_start
                prev_end = next_start = temp_end = 0
            else:
                current_speech["end"] = window_size_samples * i
                speeches.append(current_speech)
                current_speech = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

        if (speech_prob < neg_threshold) and triggered:
            if not temp_end:
                temp_end = window_size_samples * i
            # condition to avoid cutting in very short silence
            if (window_size_samples * i) - temp_end > min_silence_samples_at_max_speech:
                prev_end = temp_end
            if (window_size_samples * i) - temp_end < min_silence_samples:
                continue
            else:
                current_speech["end"] = temp_end
                if (
                    current_speech["end"] - current_speech["start"]
                ) > min_speech_samples:
                    speeches.append(current_speech)
                current_speech = {}
                prev_end = next_start = temp_end = 0
                triggered = False
                continue

    if (
        current_speech
        and (audio_length_samples - current_speech["start"]) > min_speech_samples
    ):
        current_speech["end"] = audio_length_samples
        speeches.append(current_speech)

    for i, speech in enumerate(speeches):
        if i == 0:
            speech["start"] = int(max(0, speech["start"] - speech_pad_samples))
        if i != len(speeches) - 1:
            silence_duration = speeches[i + 1]["start"] - speech["end"]
            if silence_duration < 2 * speech_pad_samples:
                speech["end"] += int(silence_duration // 2)
                speeches[i + 1]["start"] = int(
                    max(0, speeches[i + 1]["start"] - silence_duration // 2)
                )
            else:
                speech["end"] = int(
                    min(audio_length_samples, speech["end"] + speech_pad_samples)
                )
                speeches[i + 1]["start"] = int(
                    max(0, speeches[i + 1]["start"] - speech_pad_samples)
                )
        else:
            speech["end"] = int(
                min(audio_length_samples, speech["end"] + speech_pad_samples)
            )

    return speeches


@functools.lru_cache(maxsize=1)
def get_vad_model() -> "SileroVADModel":
    return SileroVADModel(
        os.fspath(assets_dir() / _ENCODER_FILE),
        os.fspath(assets_dir() / _DECODER_FILE),
    )


class SileroVADModel:
    def __init__(self, encoder_path, decoder_path):
        import onnxruntime

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.enable_cpu_mem_arena = False
        opts.log_severity_level = 4

        self.encoder_session = onnxruntime.InferenceSession(
            encoder_path,
            providers=["CPUExecutionProvider"],
            sess_options=opts,
        )
        self.decoder_session = onnxruntime.InferenceSession(
            decoder_path,
            providers=["CPUExecutionProvider"],
            sess_options=opts,
        )

    def __call__(
        self, audio: np.ndarray, num_samples: int = 512, context_size_samples: int = 64
    ):
        assert (
            audio.ndim == 2
        ), "Input should be a 2D array with size (batch_size, num_samples)"
        assert (
            audio.shape[1] % num_samples == 0
        ), "Input size should be a multiple of num_samples"

        batch_size = audio.shape[0]

        state = np.zeros((2, batch_size, 128), dtype="float32")
        context = np.zeros(
            (batch_size, context_size_samples),
            dtype="float32",
        )

        batched_audio = audio.reshape(batch_size, -1, num_samples)
        context = batched_audio[..., -context_size_samples:]
        context[:, -1] = 0
        context = np.roll(context, 1, 1)
        batched_audio = np.concatenate([context, batched_audio], 2)

        batched_audio = batched_audio.reshape(-1, num_samples + context_size_samples)

        encoder_batch_size = 10000
        num_segments = batched_audio.shape[0]
        encoder_outputs = []
        for i in range(0, num_segments, encoder_batch_size):
            encoder_output = self.encoder_session.run(
                None, {"input": batched_audio[i : i + encoder_batch_size]}
            )[0]
            encoder_outputs.append(encoder_output)

        encoder_output = np.concatenate(encoder_outputs, axis=0)
        encoder_output = encoder_output.reshape(batch_size, -1, 128)

        decoder_outputs = []
        for window in np.split(encoder_output, encoder_output.shape[1], axis=1):
            out, state = self.decoder_session.run(
                None, {"input": window.squeeze(1), "state": state}
            )
            decoder_outputs.append(out)

        out = np.stack(decoder_outputs, axis=1).squeeze(-1)
        return out
