"""
searcher.py
===========
Full-text search across all saved Markdown transcript files.

The search engine supports:
* **Case-insensitive keyword matching** (default)
* **Regex pattern matching** (opt-in)
* **Context window** — configurable number of lines returned around each match
* **Timestamp extraction** — when a match is found in a timestamped line,
  the ``[HH:MM:SS]`` anchor is extracted and included in the result so the
  user can jump directly to that point in the video.
* **Multi-file scan** — the entire transcript directory is walked recursively.

Result objects are plain dataclasses so they are easy to serialise, test,
and display.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from yt_notes.logger import get_logger

log = get_logger(__name__)

# Matches the bold timestamp prefix written by formatter.py:  **[HH:MM:SS]**
_TS_RE = re.compile(r"\*\*\[(\d{2}:\d{2}:\d{2})\]\*\*")

# Default number of surrounding lines included for context
DEFAULT_CONTEXT_LINES: int = 2


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """
    A single search hit within a transcript file.

    Attributes:
        filepath:  Absolute path to the ``.md`` file.
        title:     Human-readable title derived from the filename.
        line_no:   1-based line number of the match.
        timestamp: Video timestamp extracted from the matching line, or
                   ``None`` if the file has no timestamps.
        snippet:   A short excerpt of the matched line (up to 200 chars).
        context:   Surrounding lines for additional context.
    """

    filepath: Path
    title:    str
    line_no:  int
    timestamp: str | None
    snippet:   str
    context:   list[str] = field(default_factory=list)

    def format(self) -> str:
        """
        Render the result as a human-readable multi-line string.

        Returns:
            A formatted string suitable for printing to the terminal.
        """
        ts_part = f" @ {self.timestamp}" if self.timestamp else ""
        header = f"📄 {self.title}{ts_part}  (line {self.line_no})"
        divider = "─" * min(len(header), 80)
        ctx_block = "\n".join(f"  {ln}" for ln in self.context) if self.context else ""
        parts = [header, divider, f"  → {self.snippet}"]
        if ctx_block:
            parts.append(ctx_block)
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Core search logic
# ---------------------------------------------------------------------------

def _iter_matches(
    lines:   list[str],
    pattern: re.Pattern[str],
    context: int,
) -> Iterator[tuple[int, str | None, str, list[str]]]:
    """
    Yield ``(line_no, timestamp, snippet, context_lines)`` for every line that
    matches *pattern*.

    Args:
        lines:   All lines in the file (1-indexed externally, 0-indexed here).
        pattern: Compiled regex to match against each line.
        context: Number of surrounding lines to include on each side.

    Yields:
        Tuples of ``(1-based line number, timestamp or None, snippet, context)``.
    """
    for idx, line in enumerate(lines):
        if not pattern.search(line):
            continue

        line_no = idx + 1

        # Extract timestamp from the line if present
        ts_match = _TS_RE.search(line)
        timestamp = ts_match.group(1) if ts_match else None

        # Build snippet (strip Markdown bold syntax, truncate)
        clean = _TS_RE.sub("", line).strip()
        snippet = clean[:200] + ("…" if len(clean) > 200 else "")

        # Gather surrounding context lines
        start = max(0, idx - context)
        end   = min(len(lines), idx + context + 1)
        ctx = [
            _TS_RE.sub("", lines[i]).strip()
            for i in range(start, end)
            if i != idx
        ]

        yield line_no, timestamp, snippet, ctx


def search(
    query:       str,
    search_dir:  Path,
    use_regex:   bool = False,
    context:     int  = DEFAULT_CONTEXT_LINES,
    max_results: int  = 50,
) -> list[SearchResult]:
    """
    Search all ``.md`` files in *search_dir* for *query*.

    Args:
        query:       Keyword or regex pattern to search for.
        search_dir:  Root directory containing transcript ``.md`` files.
        use_regex:   If ``True``, treat *query* as a regular expression.
                     If ``False`` (default), the query is matched literally
                     and case-insensitively.
        context:     Number of lines to include above and below each match.
        max_results: Cap on total results returned across all files.

    Returns:
        A list of :class:`SearchResult` objects, ordered by file name then
        line number.

    Raises:
        re.error: If ``use_regex=True`` and *query* is not a valid regex.
        FileNotFoundError: If *search_dir* does not exist.
    """
    if not search_dir.exists():
        raise FileNotFoundError(
            f"Transcript directory not found: {search_dir}\n"
            "Run 'python -m yt_notes download' first."
        )

    # Compile the search pattern once
    if use_regex:
        pattern = re.compile(query)
    else:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    results: list[SearchResult] = []
    md_files = sorted(search_dir.rglob("*.md"))

    if not md_files:
        log.warning("No .md files found in %s", search_dir)
        return results

    log.info("Searching %d files for %r…", len(md_files), query)

    for filepath in md_files:
        if len(results) >= max_results:
            log.debug("Reached max_results=%d — stopping early.", max_results)
            break

        try:
            text  = filepath.read_text(encoding="utf-8")
            lines = text.splitlines()
        except OSError as exc:
            log.warning("Cannot read %s: %s", filepath, exc)
            continue

        title = filepath.stem  # filename without .md extension

        for line_no, timestamp, snippet, ctx in _iter_matches(lines, pattern, context):
            results.append(
                SearchResult(
                    filepath  = filepath,
                    title     = title,
                    line_no   = line_no,
                    timestamp = timestamp,
                    snippet   = snippet,
                    context   = ctx,
                )
            )
            if len(results) >= max_results:
                break

    log.info("Search complete — %d result(s) found.", len(results))
    return results
