"""
downloader.py
=============
Handles all interaction with the YouTube Transcript API.

Key design decisions
--------------------
* **Resume support** — files that already exist on disk are skipped.
* **Rate-limit safety** — a random delay between requests avoids triggering
  Google's automated bot detection.
* **Exponential back-off** — transient network errors are retried up to
  ``settings.max_retries`` times before the video is logged as failed and
  execution continues with the next one.
* **Language priority** — the module tries languages in the order defined in
  ``settings.lang_priority`` before falling back to the first available track.
* **Safe filenames** — video titles are sanitised to remove characters that
  are illegal on Windows, macOS, and Linux file systems.
"""

from __future__ import annotations

import json
import re
import time
import random
from pathlib import Path
from typing import Any

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from yt_notes.config import settings, DEFAULT_LECTURES
from yt_notes.formatter import format_transcript
from yt_notes.logger import get_logger

log = get_logger(__name__)

# Characters forbidden in file names on any major OS
_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|]')


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def sanitise_filename(name: str) -> str:
    """
    Replace characters that are illegal in file names with underscores.

    Args:
        name: Raw string (e.g. a video title).

    Returns:
        A safe filename string without extension.

    Examples:
        >>> sanitise_filename("Design: Patterns & Anti-patterns")
        'Design_ Patterns & Anti-patterns'
    """
    return _FORBIDDEN_CHARS.sub("_", name).strip()


def extract_video_id(url: str) -> str:
    """
    Extract the YouTube video ID from a URL.

    Supports the common ``watch?v=`` format and ``youtu.be/`` short links.

    Args:
        url: Full YouTube URL.

    Returns:
        The 11-character video ID string.

    Raises:
        ValueError: If the video ID cannot be parsed from the URL.

    Examples:
        >>> extract_video_id("https://www.youtube.com/watch?v=abc123XYZ12")
        'abc123XYZ12'
        >>> extract_video_id("https://youtu.be/abc123XYZ12")
        'abc123XYZ12'
    """
    # Pattern matches both watch?v= and youtu.be/ formats
    pattern = re.compile(
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})"
    )
    match = pattern.search(url)
    if not match:
        raise ValueError(f"Cannot extract video ID from URL: {url!r}")
    return match.group(1)


def load_source(source_path: Path | None) -> dict[str, str]:
    """
    Load the title→URL mapping from a JSON file or fall back to the built-in
    lecture catalogue.

    The JSON file must be an object whose keys are lecture titles and values
    are YouTube URLs, e.g.::

        {
            "My Lecture": "https://www.youtube.com/watch?v=XXXXXXXXXXX"
        }

    Args:
        source_path: Path to a ``.json`` file, or ``None`` to use the default
                     ``DEFAULT_LECTURES`` catalogue from ``config.py``.

    Returns:
        A ``dict[title, url]`` mapping.

    Raises:
        FileNotFoundError: If ``source_path`` is provided but does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    if source_path is None:
        log.debug("No --source flag; using built-in DEFAULT_LECTURES catalogue.")
        return DEFAULT_LECTURES

    log.info("Loading lecture list from %s", source_path)
    with source_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"{source_path} must contain a JSON object (dict), got {type(data).__name__}.")

    return data


# ---------------------------------------------------------------------------
# Core download logic
# ---------------------------------------------------------------------------

def _fetch_transcript(api: YouTubeTranscriptApi, video_id: str) -> list[Any]:
    """
    Fetch the best available transcript for a video, honouring the configured
    language priority list.

    Tries each language in ``settings.lang_priority`` in order, then falls
    back to the first track in whatever order the API returns them.

    Args:
        api:      Initialised ``YouTubeTranscriptApi`` instance.
        video_id: 11-character YouTube video identifier.

    Returns:
        A list of raw transcript segment objects.

    Raises:
        NoTranscriptFound:   No transcript exists in any language.
        TranscriptsDisabled: Transcripts are disabled for this video.
        VideoUnavailable:    The video is private, deleted, or geo-blocked.
    """
    transcript_list = api.list(video_id)

    # Try preferred languages first
    try:
        transcript = transcript_list.find_transcript(settings.lang_priority)
        log.debug("Transcript found in preferred language for %s", video_id)
    except NoTranscriptFound:
        # Fall back to the first available track
        available = list(transcript_list)
        if not available:
            raise
        transcript = available[0]
        log.debug(
            "Preferred languages not found; using '%s' track for %s",
            transcript.language_code,
            video_id,
        )

    return transcript.fetch()


def _retry_fetch(
    api: YouTubeTranscriptApi,
    video_id: str,
    title: str,
) -> list[Any] | None:
    """
    Attempt to fetch a transcript with exponential back-off on transient errors.

    Known permanent errors (disabled transcripts, private videos) are caught
    immediately without retrying.

    Args:
        api:      Initialised ``YouTubeTranscriptApi`` instance.
        video_id: YouTube video identifier.
        title:    Human-readable title (used in log messages only).

    Returns:
        A list of transcript segment objects, or ``None`` if all attempts fail.
    """
    permanent_errors = (TranscriptsDisabled, VideoUnavailable)

    for attempt in range(1, settings.max_retries + 1):
        try:
            return _fetch_transcript(api, video_id)
        except permanent_errors as exc:
            log.warning(
                "Permanent error for '%s' (%s): %s — skipping.",
                title, video_id, exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — broad catch is intentional
            wait = settings.retry_base * (2 ** (attempt - 1))  # exponential back-off
            if attempt < settings.max_retries:
                log.warning(
                    "Attempt %d/%d failed for '%s': %s. Retrying in %.1f s…",
                    attempt, settings.max_retries, title, exc, wait,
                )
                time.sleep(wait)
            else:
                log.error(
                    "All %d attempts failed for '%s' (%s): %s",
                    settings.max_retries, title, video_id, exc,
                )
                return None

    return None  # unreachable, but satisfies type checker


# ---------------------------------------------------------------------------
# Batch download entry point
# ---------------------------------------------------------------------------

def download_transcripts(
    video_dict: dict[str, str],
    output_dir: Path,
    keep_timestamps: bool = True,
) -> dict[str, str]:
    """
    Download, format, and save transcripts for every entry in *video_dict*.

    Progress is printed to the console via the ``rich`` logger.  Files that
    already exist on disk are skipped (resume support).

    Args:
        video_dict:      Mapping of ``{title: youtube_url}``.
        output_dir:      Directory in which ``.md`` files are saved.
                         Created automatically if it does not exist.
        keep_timestamps: Passed through to :func:`~yt_notes.formatter.format_transcript`.

    Returns:
        A summary dict with two keys:

        - ``"saved"``  — list of filenames successfully written.
        - ``"skipped"`` — list of filenames that already existed.
        - ``"failed"``  — list of titles that could not be downloaded.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    api = YouTubeTranscriptApi()

    saved:   list[str] = []
    skipped: list[str] = []
    failed:  list[str] = []

    total = len(video_dict)
    for index, (title, url) in enumerate(video_dict.items(), start=1):
        safe_name = sanitise_filename(title)
        filepath = output_dir / f"{safe_name}.md"

        log.info("[%d/%d] %s", index, total, title)

        # ── Resume: skip already-downloaded files ────────────────────────────
        if filepath.exists():
            log.info("  ⏩ Already exists — skipping.")
            skipped.append(safe_name)
            continue

        # ── Extract video ID ─────────────────────────────────────────────────
        try:
            video_id = extract_video_id(url)
        except ValueError as exc:
            log.error("  ❌ Bad URL for '%s': %s", title, exc)
            failed.append(title)
            continue

        # ── Fetch transcript with retries ────────────────────────────────────
        segments = _retry_fetch(api, video_id, title)
        if segments is None:
            failed.append(title)
        else:
            # ── Format and write ─────────────────────────────────────────────
            try:
                markdown = format_transcript(
                    segments,
                    title=title,
                    url=url,
                    keep_timestamps=keep_timestamps,
                )
                filepath.write_text(markdown, encoding="utf-8")
                log.info("  ✅ Saved → %s", filepath)
                saved.append(safe_name)
            except Exception as exc:  # noqa: BLE001
                log.error("  ❌ Failed to write '%s': %s", filepath, exc)
                failed.append(title)

        # ── Rate-limit-safe random delay ─────────────────────────────────────
        if index < total:
            delay = random.uniform(settings.delay_min, settings.delay_max)
            log.debug("  😴 Sleeping %.1f s before next request…", delay)
            time.sleep(delay)

    # ── Final summary ────────────────────────────────────────────────────────
    log.info(
        "Done — saved: %d | skipped: %d | failed: %d",
        len(saved), len(skipped), len(failed),
    )
    if failed:
        log.warning("Failed titles:\n  %s", "\n  ".join(failed))

    return {"saved": saved, "skipped": skipped, "failed": failed}
