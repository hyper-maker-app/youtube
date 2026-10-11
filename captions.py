"""Karaoke captions: word timings -> grouped .ass, rendered by libass.

Traps already solved here, each verified by rendering a real frame:
  * WrapStyle 2 does not wrap, it CLIPS horizontally, so long words lose their tail.
    WrapStyle 0 plus a <=3 word / <=22 char group is what actually fits 1080px.
  * The ass filter needs BOTH forward slashes AND an escaped drive colon AND single
    quotes around the whole value: filename='C\\:/path/to/subs.ass'. Any one of the
    three missing and ffmpeg reports "No option name near '/Users/...'".
  * Overlapping Dialogue events are not merged by libass, they are stacked on separate
    lines, so every event must end exactly where the next one starts.
  * libass colours are BGR, not RGB.
  * edge-tts WordBoundary strips punctuation from the token it reports, so sentence
    detection reads the `source` token that generator.assign_emphasis attaches.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import config

# A group ends here even if it is under the word/char limit, so a caption never straddles
# two sentences.
_HARD_BREAK = re.compile(r"[.!?…]$")
_SOFT_BREAK = re.compile(r"[,;:—]$")
_TRAILING = re.compile(r"[.,!?;:…—\"')\]]+$")
_LEADING = re.compile(r"^[\"'(\[“‘]+")

# Python's str.upper maps "i" to "I"; Turkish needs the dotted capital.
_TR_UPPER = str.maketrans({"i": "İ", "ı": "I"})


def _display(token: str, lang: str | None) -> str:
    """Screen form of a word: no surrounding punctuation, upper case for the locale."""
    clean = _LEADING.sub("", _TRAILING.sub("", token))
    clean = clean or token
    if (lang or config.DEFAULT_LANG).lower() == "tr":
        return clean.translate(_TR_UPPER).upper()
    return clean.upper()


def _ass_time(seconds: float) -> str:
    """h:mm:ss.cc — ASS uses centiseconds and a single-digit hour."""
    seconds = max(0.0, seconds)
    h, rem = divmod(seconds, 3600.0)
    m, s = divmod(rem, 60.0)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    """Protect libass override syntax in narration text."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _punctuated(word: dict) -> str:
    """The token as written in the narration, which is the only place punctuation lives."""
    return str(word.get("source") or word.get("text") or "").strip()


def _is_longform_caption_mode(is_longform: bool | None = None) -> bool:
    if is_longform is not None:
        return bool(is_longform)
    return bool(
        getattr(config, "LONGFORM_MODE", False)
        or getattr(config, "IS_EXPLORER_FORMAT", False)
        or os.getenv("LONGFORM_MODE", "").casefold() in {"1", "true", "yes"}
        or os.getenv("PRODUCTION_FORMAT", "").casefold() == "longform"
        or getattr(config, "WIDTH", 1080) > getattr(config, "HEIGHT", 1920)
    )


def _speaker_key(word: dict) -> tuple[str, str]:
    speaker = str(word.get("speaker") or "").strip().casefold()
    role = str(word.get("role") or "").strip()
    if not speaker:
        if role.casefold().startswith(("witness", "historical_witness", "interviewee")):
            speaker = "witness"
        else:
            speaker = "nova"
    label = str(word.get("speaker_label") or "").strip()
    if not label:
        if speaker == "witness" and ":" in role:
            label = role.split(":", 1)[1].strip()
        elif speaker == "witness":
            label = "Historical Witness"
        else:
            label = getattr(config, "EXPLORER_CHARACTER_NAME", "Nova") or "Nova"
    return speaker, label


def group_words(
    words: list[dict],
    lang: str | None = None,
    max_words: int | None = None,
    max_chars: int | None = None,
    *,
    is_longform: bool | None = None,
) -> list[list[dict]]:
    """Split word timings into caption-sized groups, at punctuation or speaker change where possible."""
    longform = _is_longform_caption_mode(is_longform)
    if max_words is None:
        max_words = 7 if longform else config.CAPTION_MAX_WORDS
    if max_chars is None:
        max_chars = 52 if longform else config.CAPTION_MAX_CHARS

    groups: list[list[dict]] = []
    current: list[dict] = []
    width = 0
    current_speaker: tuple[str, str] | None = None

    for w in words:
        shown = _display(str(w.get("text", "")).strip(), lang)
        if not shown:
            continue
        spk = _speaker_key(w) if longform else None
        # +1 for the space that will join it to the previous token.
        cost = len(shown) + (1 if current else 0)
        speaker_changed = bool(longform and current and spk != current_speaker)
        if current and (speaker_changed or len(current) >= max_words or width + cost > max_chars):
            groups.append(current)
            current, width = [], 0
            cost = len(shown)

        current.append(w)
        current_speaker = spk
        width += cost

        raw = _punctuated(w)
        if _HARD_BREAK.search(raw) or (len(current) >= 2 and _SOFT_BREAK.search(raw)):
            groups.append(current)
            current, width = [], 0
            current_speaker = None

    if current:
        groups.append(current)
    return groups


def _group_events(
    group: list[dict],
    group_end: float,
    lang: str | None,
    *,
    longform: bool = False,
) -> list[tuple[float, float, str, str]]:
    """One Dialogue line per word: the whole group is on screen, one word is highlighted."""
    if not longform:
        shown = [_ass_escape(_display(str(w.get("text", "")).strip(), lang)) for w in group]
        active_colour = config.CAPTION_ACTIVE_COLOUR
        scale = config.CAPTION_EMPHASIS_SCALE

        events: list[tuple[float, float, str, str]] = []
        for i, word in enumerate(group):
            start = float(word.get("start") or 0.0)
            end = float(group[i + 1]["start"]) if i + 1 < len(group) else group_end

            parts = list(shown)
            if word.get("is_emphasis"):
                parts[i] = (
                    f"{{\\c{active_colour}\\fscx{scale}\\fscy{scale}}}{shown[i]}{{\\r}}"
                )
            else:
                parts[i] = f"{{\\c{active_colour}}}{shown[i]}{{\\r}}"
            events.append((start, end, "Pop", " ".join(parts)))
        return events

    # 16:9 Longform mode: distinct styling and speaker tags for Nova vs Historical Witness
    speaker, label = _speaker_key(group[0])
    is_witness = (speaker == "witness")
    style_name = "WitnessSub" if is_witness else "NovaSub"
    # libass BGR colors:
    # Nova tag: cyan-gold (&H00FFD447), active word: warm cyan (&H00FFE680)
    # Witness tag: amber-orange (&H0047B8FF), active word: bright gold (&H0000D7FF)
    if is_witness:
        clean_lbl = re.sub(r"\s*\([^)]*\)", "", label).strip().upper()
        tag = f"TANIK / WITNESS — {clean_lbl}" if clean_lbl and clean_lbl != "HISTORICAL WITNESS" else "WITNESS"
        prefix = f"{{\\c&H0047B8FF&\\b1}}[{_ass_escape(tag)}]:{{\\rWitnessSub}} "
        active_col = "&H0000D7FF&"
    else:
        host_label = _ass_escape(label.upper())
        prefix = f"{{\\c&H00FFD447&\\b1}}[{host_label}]:{{\\rNovaSub}} "
        active_col = "&H00FFE680&"

    shown_tokens: list[str] = []
    for w in group:
        raw_tok = _punctuated(w) or str(w.get("text", "")).strip()
        shown_tokens.append(_ass_escape(raw_tok))

    events = []
    for i, word in enumerate(group):
        start = float(word.get("start") or 0.0)
        end = float(group[i + 1]["start"]) if i + 1 < len(group) else group_end
        parts = list(shown_tokens)
        if word.get("is_emphasis"):
            parts[i] = f"{{\\c{active_col}\\b1}}{shown_tokens[i]}{{\\r{style_name}}}"
        else:
            parts[i] = f"{{\\c{active_col}}}{shown_tokens[i]}{{\\r{style_name}}}"
        line_text = prefix + " ".join(parts)
        events.append((start, end, style_name, line_text))
    return events


def _resolve_era_stamp(topic: str | None) -> str:
    try:
        from services.character import detect_era, get_era_witness
        era = detect_era(topic or "")
        w1 = get_era_witness(era, 1)
        stamp = w1.get("location_stamp") or "HISTORICAL EXPEDITION — ANTIQUITY"
        if topic and stamp == "HISTORICAL SITE — ANTIQUITY":
            clean_t = re.sub(r"[^\w\s-]", "", topic).strip().upper()[:32]
            return f"{clean_t} — ANTIQUITY"
        return stamp
    except Exception:
        return "HISTORICAL EXPEDITION — ANTIQUITY"


def build_ass(
    words: list[dict],
    total_duration: float | None = None,
    lang: str | None = None,
    *,
    topic: str | None = None,
    is_longform: bool | None = None,
) -> str:
    """Render the full .ass document for one voiceover."""
    timed = [
        w for w in words
        if str(w.get("text", "")).strip() and w.get("start") is not None
    ]
    if not timed:
        raise ValueError("No timed words to caption.")

    if total_duration is None:
        raise ValueError("Caption generation requires the persisted timeline duration")
    limit = total_duration
    longform = _is_longform_caption_mode(is_longform)
    groups = group_words(timed, lang, is_longform=longform)

    events: list[str] = []
    if longform:
        # 1. Persistent subtle top-right watermark (like Zaman Yolcusu Defne)
        char_name = (getattr(config, "EXPLORER_CHARACTER_NAME", "Nova") or "Nova").upper()
        events.append(
            f"Dialogue: 2,{_ass_time(0.0)},{_ass_time(limit)},BrandWatermark,,0,0,0,,TIME TRAVELER {char_name}"
        )
        # 2. Opening Historical Era & Location Stamp (bottom-right, 0.4s -> 7.5s)
        stamp_end = min(limit, 7.5)
        if stamp_end > 0.6:
            stamp_text = _ass_escape(_resolve_era_stamp(topic))
            events.append(
                f"Dialogue: 2,{_ass_time(0.4)},{_ass_time(stamp_end)},EraStamp,,0,0,0,,{{\\fad(350,450)}}📍 {stamp_text}"
            )

    cursor = 0.0  # last emitted end; subtitle events on Layer 0 must never overlap
    for gi, group in enumerate(groups):
        last = group[-1]
        group_end = float(last.get("end") or last["start"]) + config.CAPTION_LEAD_IN
        if gi + 1 < len(groups):
            group_end = min(group_end, float(groups[gi + 1][0]["start"]))
        group_end = min(limit, max(group_end, float(group[0]["start"]) + config.CAPTION_MIN_DURATION))

        if longform:
            spk, lbl = _speaker_key(group[0])
            if spk == "witness":
                g_start = max(0.0, float(group[0].get("start") or 0.0))
                if group_end - g_start >= 0.15:
                    badge_lbl = _ass_escape(lbl.upper())
                    events.append(
                        f"Dialogue: 1,{_ass_time(g_start)},{_ass_time(group_end)},WitnessBadge,,0,0,0,,🎙️ HISTORICAL EYEWITNESS: {badge_lbl}"
                    )

        for i, (start, end, style_name, text) in enumerate(_group_events(group, group_end, lang, longform=longform)):
            # Only the first word of a group leads in; the rest inherit the previous end.
            start = max(cursor, start - config.CAPTION_LEAD_IN) if i == 0 else max(cursor, start)
            end = min(limit, end)
            if end - start < 0.02:
                continue
            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},{style_name},,0,0,0,,{text}"
            )
            cursor = end

    if not events:
        raise ValueError("Word timings produced no caption events.")

    bold = -1 if config.CAPTION_BOLD else 0
    play_x = 1920 if (longform and config.WIDTH < config.HEIGHT) else config.WIDTH
    play_y = 1080 if (longform and config.WIDTH < config.HEIGHT) else config.HEIGHT
    longform_styles = ""
    if longform:
        longform_styles = (
            f"\nStyle: NovaSub,{config.CAPTION_FONT},40,&H00FFFFFF,&H000000FF,"
            f"&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,80,80,52,1"
            f"\nStyle: WitnessSub,{config.CAPTION_FONT},40,&H00C8F0FF,&H000000FF,"
            f"&H00001828,&H96000000,-1,-1,0,0,100,100,0,0,1,3,2,2,80,80,52,1"
            f"\nStyle: WitnessBadge,{config.CAPTION_FONT},26,&H0047B8FF,&H000000FF,"
            f"&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,2,1,1,80,80,132,1"
            f"\nStyle: EraStamp,{config.CAPTION_FONT},30,&H0080E6FF,&H000000FF,"
            f"&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,3,2,3,64,64,125,1"
            f"\nStyle: BrandWatermark,{config.CAPTION_FONT},24,&H55FFFFFF,&H000000FF,"
            f"&H55000000,&H00000000,-1,0,0,0,100,100,2,0,1,1,1,9,48,48,36,1"
        )
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_x}
PlayResY: {play_y}
WrapStyle: {config.CAPTION_WRAP_STYLE}
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, \
BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, \
BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,{config.CAPTION_FONT},{config.CAPTION_FONT_SIZE},&H00FFFFFF,&H000000FF,\
&H00000000,&H64000000,{bold},0,0,0,100,100,0,0,1,{config.CAPTION_OUTLINE},\
{config.CAPTION_SHADOW},2,{config.CAPTION_MARGIN_H},{config.CAPTION_MARGIN_H},\
{config.CAPTION_MARGIN_V},1{longform_styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header + "\n".join(events) + "\n"


def write_ass(
    words: list[dict],
    out_path: Path,
    total_duration: float | None = None,
    lang: str | None = None,
    *,
    topic: str | None = None,
    is_longform: bool | None = None,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        build_ass(words, total_duration, lang, topic=topic, is_longform=is_longform),
        encoding="utf-8",
    )
    return out_path


def escape_for_filter(path: Path) -> str:
    """Quote and escape a path so the ass filter accepts it on Windows.

    All three transforms are load-bearing (verified against ffmpeg 7.1): backslashes
    become forward slashes, the drive colon is escaped so it is not read as an option
    separator, and the result is single-quoted so spaces and parentheses survive.
    """
    forward = str(Path(path).resolve()).replace("\\", "/")
    return "'" + forward.replace(":", "\\:") + "'"


def ass_filter(path: Path) -> str:
    """The filter fragment to append to the video chain."""
    spec = f"ass=filename={escape_for_filter(path)}"
    fonts = config.CAPTION_FONTS_DIR
    if fonts and Path(fonts).exists():
        spec += f":fontsdir={escape_for_filter(Path(fonts))}"
    return spec
