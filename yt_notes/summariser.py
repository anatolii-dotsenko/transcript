"""
summariser.py
=============
AI-powered transcript summarisation using Google Gemini.

The module is intentionally optional — if no API key is configured, calls to
:func:`summarise_file` raise a clear :class:`RuntimeError` rather than failing
silently.  This keeps the rest of the application fully functional for users
who do not have (or do not want) an AI integration.

Student note
------------
Google Gemini offers a **free tier** through Google AI Studio:
https://aistudio.google.com/app/apikey

The ``gemini-1.5-flash`` model is used by default because it has the largest
free-tier quota and a 1 M-token context window — more than enough for any
lecture transcript.
"""

from __future__ import annotations

from pathlib import Path

from yt_notes.config import settings
from yt_notes.logger import get_logger

log = get_logger(__name__)

# Gemini model to use. Flash is free-tier-friendly; swap for Pro if needed.
_MODEL_NAME = "models/gemini-2.5-flash"

# Summarisation prompt template
_PROMPT_TEMPLATE = """\
You are an expert study assistant. Below is the full transcript of a lecture.

Please produce:
1. A concise **executive summary** (3–5 sentences) of the main topic.
2. A bulleted list of **key concepts and terms** introduced in the lecture.
3. Three **study questions** that test understanding of the core ideas.

---
TRANSCRIPT:
{transcript}
---

Respond in the same language as the transcript.
"""


def _require_api_key() -> str:
    """
    Return the configured Gemini API key or raise a descriptive error.

    Returns:
        The API key string.

    Raises:
        RuntimeError: If ``GEMINI_API_KEY`` is not set in the environment.
    """
    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set.\n"
            "Add it to your .env file to enable AI summarisation.\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )
    return settings.gemini_api_key


def summarise_text(transcript_text: str) -> str:
    """
    Send *transcript_text* to Gemini and return a structured Markdown summary.

    Args:
        transcript_text: Plain or Markdown transcript content.

    Returns:
        A Markdown-formatted summary string from Gemini.

    Raises:
        RuntimeError: If the Gemini API key is not configured.
        google.api_core.exceptions.GoogleAPIError: On API-level errors.
    """
    import google.generativeai as genai  # lazy import — not required globally

    api_key = _require_api_key()
    genai.configure(api_key=api_key)

    model  = genai.GenerativeModel(_MODEL_NAME)
    prompt = _PROMPT_TEMPLATE.format(transcript=transcript_text)

    log.info("Sending %d characters to Gemini (%s)…", len(transcript_text), _MODEL_NAME)
    response = model.generate_content(prompt)
    log.info("Gemini response received.")

    return response.text


def summarise_file(filepath: Path) -> str:
    """
    Read a saved transcript file and return an AI-generated summary.

    The summary is also written to a sibling file with the suffix
    ``_summary.md`` so it can be reviewed later without re-querying Gemini.

    Args:
        filepath: Path to a ``.md`` transcript file.

    Returns:
        The Markdown summary string.

    Raises:
        FileNotFoundError: If *filepath* does not exist.
        RuntimeError:      If the Gemini API key is not configured.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Transcript file not found: {filepath}")

    log.info("Summarising: %s", filepath.name)
    transcript_text = filepath.read_text(encoding="utf-8")

    summary = summarise_text(transcript_text)

    # Write summary to a sibling file
    summary_path = filepath.with_name(filepath.stem + "_summary.md")
    summary_path.write_text(
        f"# Summary — {filepath.stem}\n\n{summary}",
        encoding="utf-8",
    )
    log.info("Summary saved → %s", summary_path)

    return summary
