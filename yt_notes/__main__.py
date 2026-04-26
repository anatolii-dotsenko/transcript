"""
__main__.py
===========
Command-line interface for yt_notes.

Usage::

    python -m yt_notes download [--source PATH] [--no-timestamps]
    python -m yt_notes search QUERY [--regex] [--context N] [--max N]
    python -m yt_notes summarise FILE

Run ``python -m yt_notes --help`` for full usage information.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from yt_notes.config import settings
from yt_notes.logger import get_logger

log     = get_logger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def cmd_download(args: argparse.Namespace) -> int:
    """
    Handle the ``download`` sub-command.

    Downloads transcripts for all videos in the source catalogue, skipping
    files that have already been saved.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = at least one failure).
    """
    from yt_notes.downloader import download_transcripts, load_source

    source_path = Path(args.source) if args.source else None
    try:
        video_dict = load_source(source_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error loading source:[/red] {exc}")
        return 1

    output_dir = settings.transcript_dir
    console.print(
        Panel(
            f"Downloading [bold]{len(video_dict)}[/bold] transcripts → [cyan]{output_dir}[/cyan]",
            title="yt-notes download",
        )
    )

    summary = download_transcripts(
        video_dict,
        output_dir=output_dir,
        keep_timestamps=not args.no_timestamps,
    )

    console.print(
        f"\n✅ Saved: [green]{len(summary['saved'])}[/green]  "
        f"⏩ Skipped: [yellow]{len(summary['skipped'])}[/yellow]  "
        f"❌ Failed: [red]{len(summary['failed'])}[/red]"
    )
    return 1 if summary["failed"] else 0


def cmd_search(args: argparse.Namespace) -> int:
    """
    Handle the ``search`` sub-command.

    Searches all saved transcript files for the given keyword or regex and
    prints matching results with context to the console.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = results found, 1 = no results or error).
    """
    from yt_notes.searcher import search

    try:
        results = search(
            query      = args.query,
            search_dir = settings.transcript_dir,
            use_regex  = args.regex,
            context    = args.context,
            max_results= args.max,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    if not results:
        console.print(f"[yellow]No results found for[/yellow] {args.query!r}")
        return 1

    console.print(
        Panel(
            f"[bold]{len(results)}[/bold] result(s) for [cyan]{args.query!r}[/cyan]",
            title="yt-notes search",
        )
    )
    for r in results:
        console.print(r.format())
        console.print()

    return 0


def cmd_summarise(args: argparse.Namespace) -> int:
    """
    Handle the ``summarise`` sub-command.

    Sends the transcript at *args.file* to Gemini and prints the summary.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    from yt_notes.summariser import summarise_file

    filepath = Path(args.file)
    try:
        summary = summarise_file(filepath)
    except (FileNotFoundError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1

    console.print(Panel(summary, title=f"Summary — {filepath.stem}"))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """
    Build and return the top-level argument parser with all sub-commands.

    Returns:
        A fully configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="python -m yt_notes",
        description="Local Video Transcript Manager — download, search, summarise.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── download ──────────────────────────────────────────────────────────────
    dl = sub.add_parser("download", help="Download transcripts from YouTube.")
    dl.add_argument(
        "--source", metavar="PATH",
        help="Path to a JSON file mapping titles to YouTube URLs. "
             "Omit to use the built-in lecture catalogue.",
    )
    dl.add_argument(
        "--no-timestamps", action="store_true",
        help="Strip timestamps; output flowing paragraphs instead.",
    )

    # ── search ────────────────────────────────────────────────────────────────
    se = sub.add_parser("search", help="Full-text search across transcripts.")
    se.add_argument("query", help="Keyword or regex pattern to search for.")
    se.add_argument(
        "--regex", action="store_true",
        help="Treat QUERY as a regular expression.",
    )
    se.add_argument(
        "--context", type=int, default=2, metavar="N",
        help="Number of surrounding lines shown per match (default: 2).",
    )
    se.add_argument(
        "--max", type=int, default=50, metavar="N",
        help="Maximum total results to return (default: 50).",
    )

    # ── summarise ─────────────────────────────────────────────────────────────
    sm = sub.add_parser("summarise", help="AI-summarise a transcript via Gemini.")
    sm.add_argument("file", help="Path to the .md transcript file to summarise.")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate sub-command handler."""
    parser = build_parser()
    args   = parser.parse_args()

    handlers = {
        "download":  cmd_download,
        "search":    cmd_search,
        "summarise": cmd_summarise,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))


if __name__ == "__main__":
    main()
