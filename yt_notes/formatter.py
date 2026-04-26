"""
formatter.py
============
Converts a raw list of transcript segments (as returned by
``youtube-transcript-api``) into clean, human-readable Markdown.

Two output modes are supported:

``keep_timestamps=True``  (default)
    Each segment is prefixed with a clickable timestamp anchor so readers
    can jump directly to that point in the video.
    Example::

        **[00:02:15]** This is the spoken text here.

``keep_timestamps=False``
    Timestamps are stripped; segments are joined into flowing paragraphs
    separated by blank lines every ``PARAGRAPH_BREAK_EVERY`` segments.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of segments grouped into one paragraph when timestamps are hidden
PARAGRAPH_BREAK_EVERY: int = 8

# Characters that signal the end of a sentence (used for paragraph breaks)
_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")

# Patterns to remove YouTube auto-caption noise
_NOISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\[Music\]", re.IGNORECASE),
    re.compile(r"\[Applause\]", re.IGNORECASE),
    re.compile(r"\[Laughter\]", re.IGNORECASE),
    re.compile(r"\[noise\]", re.IGNORECASE),
    re.compile(r"<[^>]+>"),    # HTML-like tags  (<c>, </c>, etc.)
    re.compile(r"&amp;"),
    re.compile(r"&nbsp;"),
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def seconds_to_timestamp(seconds: float) -> str:
    """
    Convert a float number of seconds to a ``HH:MM:SS`` string.

    Args:
        seconds: Elapsed video time in seconds.

    Returns:
        A zero-padded timestamp string, e.g. ``"00:02:15"``.

    Examples:
        >>> seconds_to_timestamp(135.4)
        '00:02:15'
        >>> seconds_to_timestamp(3661.0)
        '01:01:01'
    """
    total = int(seconds)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _clean_text(text: str) -> str:
    """
    Remove auto-caption noise and normalise whitespace from a single segment.

    Args:
        text: Raw text from a transcript segment.

    Returns:
        Cleaned text string, or an empty string if only noise remained.
    """
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub("", text)
    # Collapse internal whitespace
    text = " ".join(text.split())
    return text.strip()


def _extract_segment(segment: Any) -> tuple[float, str]:
    """
    Safely extract ``(start_time, text)`` from a segment that may be either
    a plain ``dict`` or an object with attributes (depending on the
    ``youtube-transcript-api`` version).

    Args:
        segment: A transcript segment from the API.

    Returns:
        A ``(start_seconds, raw_text)`` tuple.
    """
    if isinstance(segment, dict):
        return float(segment.get("start", 0.0)), segment.get("text", "")
    # Object-style (FetchedTranscriptSnippet in newer library versions)
    return float(getattr(segment, "start", 0.0)), getattr(segment, "text", "")


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def format_transcript(
    segments: list[Any],
    title: str,
    url: str,
    keep_timestamps: bool = True,
) -> str:
    """
    Format a list of raw transcript segments into a clean Markdown document.

    Args:
        segments:        Raw segments from ``youtube-transcript-api``.
        title:           Human-readable video title (used as H1 heading).
        url:             Original YouTube URL (embedded in the document header).
        keep_timestamps: If ``True``, each segment is prefixed with a bold
                         timestamp anchor.  If ``False``, segments are merged
                         into flowing paragraphs.

    Returns:
        A complete Markdown string ready to be written to a ``.md`` file.

    Raises:
        ValueError: If ``segments`` is empty.
    """
    if not segments:
        raise ValueError(f"No transcript segments provided for '{title}'.")

    lines: list[str] = []

    # ── Document header ──────────────────────────────────────────────────────
    lines.append(f"# {title}\n")
    lines.append(f"> 🎬 Source: <{url}>\n")
    lines.append("---\n")

    if keep_timestamps:
        lines.extend(_format_with_timestamps(segments))
    else:
        lines.extend(_format_as_paragraphs(segments))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private formatting strategies
# ---------------------------------------------------------------------------

def _format_with_timestamps(segments: list[Any]) -> list[str]:
    """
    Build Markdown lines where each segment starts with a bold timestamp.

    Args:
        segments: Raw transcript segments.

    Returns:
        List of formatted Markdown lines.
    """
    lines: list[str] = []
    for seg in segments:
        start, raw_text = _extract_segment(seg)
        text = _clean_text(raw_text)
        if not text:
            continue
        ts = seconds_to_timestamp(start)
        lines.append(f"**[{ts}]** {text}\n")
    return lines


def _format_as_paragraphs(segments: list[Any]) -> list[str]:
    """
    Merge segments into flowing paragraphs, inserting a blank line every
    ``PARAGRAPH_BREAK_EVERY`` segments or after a sentence-ending segment.

    Args:
        segments: Raw transcript segments.

    Returns:
        List of formatted Markdown lines (paragraphs separated by blank lines).
    """
    words: list[str] = []
    lines: list[str] = []
    counter = 0

    for seg in segments:
        _, raw_text = _extract_segment(seg)
        text = _clean_text(raw_text)
        if not text:
            continue

        words.append(text)
        counter += 1

        end_of_sentence = bool(_SENTENCE_END_RE.search(text))
        if counter >= PARAGRAPH_BREAK_EVERY or end_of_sentence:
            paragraph = " ".join(words)
            # Wrap at 100 chars for readability
            wrapped = textwrap.fill(paragraph, width=100)
            lines.append(wrapped + "\n")
            lines.append("")
            words = []
            counter = 0

    # Flush any remaining words
    if words:
        paragraph = " ".join(words)
        lines.append(textwrap.fill(paragraph, width=100) + "\n")

    return lines
