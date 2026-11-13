"""export.py - Formattazione dei risultati (TXT, Markdown, SRT, JSON)."""

from __future__ import annotations

from datetime import datetime


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def _srt_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _header_lines(result, prefix: str) -> list[str]:
    duration = format_timestamp(result.duration)
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    headers = [
        f"{prefix}File: {result.source_name}",
        f"{prefix}Durata: {duration}",
        f"{prefix}Lingua: {str(result.language).upper()}",
        f"{prefix}Modello: {result.model}",
    ]
    if getattr(result, "backend", "off") != "off":
        speakers = ", ".join(result.speakers) if result.speakers else "n/d"
        headers.extend([
            f"{prefix}Diarizzazione: {result.backend}",
            f"{prefix}Parlanti: {len(result.speakers)} ({speakers})",
        ])
    headers.append(f"{prefix}Generato: {date}")
    return headers


def to_txt(result) -> str:
    has_diar = getattr(result, "backend", "off") != "off"
    title = "TRASCRIZIONE CON DIARIZZAZIONE" if has_diar else "TRASCRIZIONE"
    lines = [title, "=" * 60]
    lines.extend(_header_lines(result, ""))
    lines.append("")
    lines.append("=" * 60)
    lines.append("")
    for segment in result.paragraphs:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        # Nessun timestamp nel testo: solo il parlante (se presente) e la frase.
        if has_diar and segment.get("speaker"):
            lines.append(f"{segment['speaker']}: {text}")
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_markdown(result) -> str:
    from datetime import datetime as _dt

    date = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    has_diar = getattr(result, "backend", "off") != "off"
    title = "# Trascrizione con diarizzazione" if has_diar else "# Trascrizione"

    lines = [
        title,
        "",
        f"- **File:** {result.source_name}",
        f"- **Durata:** {format_timestamp(result.duration)}",
        f"- **Lingua:** {str(result.language).upper()}",
        f"- **Modello:** {result.model}",
    ]
    if has_diar:
        speakers = ", ".join(result.speakers) if result.speakers else "n/d"
        lines.extend([
            f"- **Diarizzazione:** {result.backend}",
            f"- **Parlanti:** {len(result.speakers)} ({speakers})",
        ])
    lines.extend([
        f"- **Generato:** {date}",
        "",
        "---",
        "",
    ])

    for segment in result.paragraphs:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        # Nessun timestamp: paragrafo semplice, con il parlante in grassetto.
        if has_diar and segment.get("speaker"):
            lines.append(f"**{segment['speaker']}:** {text}")
        else:
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_subtitle_cues(
    segment: dict,
    has_diar: bool,
    max_chars: int = 42,
    max_duration: float = 4.0,
    max_words: int = 8,
) -> list[tuple[float, float, str]]:
    """Divide un segmento in battute di sottotitolo brevi e sincronizzate."""
    words = segment.get("words")
    speaker = segment.get("speaker") if has_diar else None

    if not words:
        text = segment.get("text", "").strip()
        if not text:
            return []
        text_line = f"{speaker}: {text}" if speaker else text
        return [(float(segment["start"]), float(segment["end"]), text_line)]

    cues: list[tuple[float, float, str]] = []
    current: list[dict] = []

    for i, w in enumerate(words):
        current.append(w)
        dur = float(current[-1]["end"]) - float(current[0]["start"])
        char_len = sum(len(x["text"]) for x in current) + len(current) - 1
        text_end = str(w["text"]).rstrip()

        is_hard = text_end.endswith((".", "!", "?"))
        is_soft = text_end.endswith((",", ";", ":"))
        is_long = dur >= max_duration or char_len >= max_chars or len(current) >= max_words
        pause = (
            (float(words[i + 1]["start"]) - float(w["end"]) >= 0.4)
            if i < len(words) - 1
            else False
        )

        if is_hard or pause or (is_soft and dur >= 1.5) or is_long:
            cue_text = " ".join(str(x["text"]).strip() for x in current).strip()
            if cue_text:
                text_line = f"{speaker}: {cue_text}" if speaker else cue_text
                cues.append((float(current[0]["start"]), float(current[-1]["end"]), text_line))
            current = []

    if current:
        cue_text = " ".join(str(x["text"]).strip() for x in current).strip()
        if cue_text:
            text_line = f"{speaker}: {cue_text}" if speaker else cue_text
            cues.append((float(current[0]["start"]), float(current[-1]["end"]), text_line))

    return cues


def to_srt(result) -> str:
    has_diar = getattr(result, "backend", "off") != "off"
    blocks: list[str] = []
    cue_index = 1

    for segment in result.segments:
        cues = _format_subtitle_cues(segment, has_diar)
        for start, end, text in cues:
            blocks.append(
                f"{cue_index}\n"
                f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n"
                f"{text}\n"
            )
            cue_index += 1

    return "\n".join(blocks)


def to_json(result) -> str:
    import json

    has_diar = getattr(result, "backend", "off") != "off"
    payload = {
        "source": result.source_name,
        "duration": result.duration,
        "language": result.language,
        "model": result.model,
        "diarization": result.backend if has_diar else "off",
        "speakers": result.speakers if has_diar else [],
        "segments": result.segments,
        "paragraphs": result.paragraphs,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


RENDERERS = {
    "txt": to_txt,
    "md": to_markdown,
    "markdown": to_markdown,
    "srt": to_srt,
    "json": to_json,
}


def render(result, fmt: str) -> str:
    fmt = fmt.lower()
    if fmt not in RENDERERS:
        raise ValueError(f"Formato non supportato: {fmt}")
    return RENDERERS[fmt](result)