"""merge.py - Assegna i parlanti alle frasi e raggruppa il testo."""

from __future__ import annotations

from dataclasses import dataclass

from .diarization import Turn
from .transcription import Utterance

# Intervalli Unicode delle scritture senza spazi tra le parole (CJK): tra due
# caratteri di questo tipo non va inserito alcuno spazio.
_NO_SPACE_RANGES = (
    ("\u1100", "\u11ff"),  # Hangul Jamo
    ("\u3040", "\u30ff"),  # Hiragana e Katakana
    ("\u3400", "\u4dbf"),  # CJK estensione A
    ("\u4e00", "\u9fff"),  # CJK unificati
    ("\uac00", "\ud7af"),  # Hangul sillabe
    ("\uf900", "\ufaff"),  # CJK compatibilita'
    ("\uff00", "\uffef"),  # forme a larghezza piena
)


def _is_cjk(ch: str) -> bool:
    return any(lo <= ch <= hi for lo, hi in _NO_SPACE_RANGES)


def _append_word(base: str, piece: str) -> str:
    """Concatena la parola ``piece`` a ``base`` con lo spazio corretto.

    I motori possono restituire le parole con o senza spazio iniziale. Qui si
    gestiscono entrambe le convenzioni senza duplicare o perdere spazi (era il
    difetto che incollava le parole in uscita).
    """
    if not piece:
        return base
    if not base:
        return piece.lstrip()
    if piece[0].isspace():
        return base + piece
    if _is_cjk(piece[0]) and _is_cjk(base[-1]):
        return base + piece
    return base + " " + piece


class SpeakerTimeline:
    """Mappa istanti temporali -> parlante, con fallback al piu' vicino."""

    def __init__(self, turns: list[Turn]) -> None:
        self.turns = sorted((t for t in turns if t.end > t.start), key=lambda t: t.start)
        self._starts = [t.start for t in self.turns]

    @property
    def is_empty(self) -> bool:
        return not self.turns

    def speaker_at(self, t: float) -> str:
        if not self.turns:
            return "Speaker 1"
        # Turno che contiene t (il primo, in caso di sovrapposizione)
        for turn in self.turns:
            if turn.start <= t < turn.end:
                return turn.speaker
        # Altrimenti il turno con centro piu' vicino
        return min(
            self.turns,
            key=lambda turn: min(abs(t - turn.start), abs(t - turn.end)),
        ).speaker

    def dominant(self, start: float, end: float) -> str:
        if not self.turns:
            return "Speaker 1"
        best_speaker = "Speaker 1"
        best_overlap = 0.0
        for turn in self.turns:
            overlap = min(end, turn.end) - max(start, turn.start)
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn.speaker
        if best_overlap > 0:
            return best_speaker
        return self.speaker_at((start + end) / 2.0)


def assign_speakers(utterances: list[Utterance], turns: list[Turn]) -> list[Utterance]:
    """Assegna il parlante a ogni parola/frase.

    Se sono disponibili i timestamp a livello di parola le frasi vengono
    spezzate ai cambi di parlante (accuratezza maggiore).
    """
    timeline = SpeakerTimeline(turns)
    result: list[Utterance] = []

    for utt in utterances:
        if utt.words:
            current: Utterance | None = None
            for word in utt.words:
                speaker = timeline.speaker_at((word.start + word.end) / 2.0)
                if current is not None and current.speaker == speaker:
                    current.end = max(current.end, word.end)
                    current.text = _append_word(current.text, word.text)
                    current.words.append(word)
                else:
                    if current is not None:
                        result.append(current)
                    current = Utterance(
                        start=word.start,
                        end=word.end,
                        text=word.text,
                        words=[word],
                        speaker=speaker,
                    )
            if current is not None:
                result.append(current)
        else:
            speaker = timeline.dominant(utt.start, utt.end)
            result.append(
                Utterance(
                    start=utt.start,
                    end=utt.end,
                    text=utt.text,
                    words=[],
                    speaker=speaker,
                )
            )

    cleaned: list[Utterance] = []
    for utt in result:
        text = " ".join(utt.text.split())
        if not text:
            continue
        cleaned.append(
            Utterance(
                start=utt.start, end=utt.end, text=text, words=utt.words, speaker=utt.speaker
            )
        )
    return cleaned


def relabel_speakers(utterances: list[Utterance]) -> list[str]:
    """Rinomina i parlanti in Speaker 1, Speaker 2, ... per ordine di comparsa."""
    mapping: dict[str, str] = {}
    for utt in utterances:
        raw = utt.speaker or "UNKNOWN"
        if raw not in mapping:
            mapping[raw] = f"Speaker {len(mapping) + 1}"
    for utt in utterances:
        utt.speaker = mapping.get(utt.speaker or "UNKNOWN", "Speaker 1")
    return list(mapping.values())


def group_segments(utterances: list[Utterance], gap: float = 1.0) -> list[Utterance]:
    """Unisce frasi consecutive dello stesso parlante se il gap e' piccolo."""
    if not utterances:
        return []
    ordered = sorted(utterances, key=lambda u: u.start)
    grouped: list[Utterance] = [
        Utterance(
            ordered[0].start,
            ordered[0].end,
            ordered[0].text,
            list(ordered[0].words),
            ordered[0].speaker,
        )
    ]
    for utt in ordered[1:]:
        last = grouped[-1]
        if utt.speaker == last.speaker and (utt.start - last.end) <= gap:
            last.end = max(last.end, utt.end)
            joiner = "" if last.text.endswith(("-", "’", "'")) else " "
            last.text = (last.text + joiner + utt.text).strip()
            last.words.extend(utt.words)
        else:
            grouped.append(
                Utterance(utt.start, utt.end, utt.text, list(utt.words), utt.speaker)
            )
    return grouped