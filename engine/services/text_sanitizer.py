"""Spoken Text Sanitizer & Metadata Stripper Gateway for Grok Cinematic Studio.

Guarantees that narration fed into TTS providers (Deepgram, Voyslity, ElevenLabs)
and Libass captioning engines is 100% clean spoken prose. Strips:
- Act / Scene / Part / Chapter markers (e.g., 'Act 1:', 'Scene 02 -')
- Audio, Foley, and Camera directives in brackets/parentheses (e.g., '[Sound of sirens]', '(whispering)')
- Speaker prefix tags (e.g., 'Narrator:', 'Voiceover:', 'VO:')
- Markdown formatting artifacts and lingering editorial whitespace.
"""

from __future__ import annotations

import re


# Compile high-performance regex patterns
_HEADING_PATTERN = re.compile(
    r"\b(?:Act|Scene|Part|Chapter|Bölüm)\s*(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|viii|vii|vi|iv|v|ix|x|iii|ii|i)\s*[:\-–]?\s*",
    re.IGNORECASE,
)

_MARKDOWN_HEADING_PATTERN = re.compile(
    r"#{1,6}\s*(?:Act|Scene|Part|Chapter)?\s*\d*[:\-–]?\s*",
    re.IGNORECASE,
)

# Strips any square bracketed directives (in voice scripts, brackets are ALWAYS stage/foley directions)
_ALL_BRACKETS_PATTERN = re.compile(r"\[[^\]]*\]")

_DIRECTIVE_PARENS_PATTERN = re.compile(
    r"\((?:whisper|whispering|shout|shouting|pause|beat|sigh|sighs|foley|sfx|sound|music|ambient|camera|breathing|gasp|crying)[^\)]*\)",
    re.IGNORECASE,
)

_SPEAKER_LABEL_PATTERN = re.compile(
    r"(?:^|(?<=[.!?]\s))\s*(?:Narrator|Voiceover|VO|You)\s*:\s*",
    re.IGNORECASE | re.MULTILINE,
)

_MARKDOWN_STYLING_PATTERN = re.compile(r"[*_~`]")


def sanitize_spoken_text(text: str) -> str:
    """Sanitize narration text to ensure zero meta-tokens or stage directions enter TTS.

    Args:
        text: Raw script narration string.

    Returns:
        Clean, spoken-word string ready for voice synthesis and forced alignment.
    """
    if not text:
        return ""

    cleaned = str(text)

    # 1. Remove markdown headings and headers
    cleaned = _MARKDOWN_HEADING_PATTERN.sub("", cleaned)

    # 2. Strip all square bracketed stage, audio, and visual directives
    cleaned = _ALL_BRACKETS_PATTERN.sub("", cleaned)

    # 3. Strip parenthetical vocal or sound notes
    cleaned = _DIRECTIVE_PARENS_PATTERN.sub("", cleaned)

    # 4. Strip Act / Scene / Chapter numbering prefixes (numeric or word form)
    cleaned = _HEADING_PATTERN.sub("", cleaned)

    # 5. Strip speaker labels ('Narrator:', 'Voiceover:', etc.)
    cleaned = _SPEAKER_LABEL_PATTERN.sub("", cleaned)

    # 6. Remove stray markdown styling characters (*, _, ~, `)
    cleaned = _MARKDOWN_STYLING_PATTERN.sub("", cleaned)

    # 7. Strip stray quotation marks wrapping the whole text
    cleaned = cleaned.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()

    # 8. Collapse whitespace and fix orphan punctuation
    cleaned = " ".join(cleaned.split())
    cleaned = re.sub(r"\s+([.,!?;:])", r"\1", cleaned)

    return cleaned
