"""
tests/test_searcher.py
======================
Unit tests for yt_notes.searcher.

Uses a temporary directory with synthetic .md files — no real transcripts needed.
"""

import re
import pytest
from pathlib import Path

from yt_notes.searcher import search, SearchResult, _iter_matches


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def transcript_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with two synthetic transcript files."""
    (tmp_path / "Антипатерни.md").write_text(
        "# Антипатерни\n\n"
        "**[00:00:05]** Сьогодні ми розглянемо антипатерни.\n"
        "**[00:01:00]** Перший антипатерн — God Object.\n"
        "**[00:02:30]** Другий антипатерн — Spaghetti Code.\n",
        encoding="utf-8",
    )
    (tmp_path / "Dependency_Injection.md").write_text(
        "# Dependency Injection\n\n"
        "**[00:00:00]** Dependency Injection спрощує тестування.\n"
        "**[00:05:00]** Фреймворки: Spring, Dagger, Koin.\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------

class TestSearch:
    def test_finds_keyword_case_insensitive(self, transcript_dir):
        results = search("антипатерн", transcript_dir)
        assert len(results) >= 2
        assert all("Антипатерн" in r.filepath.name for r in results)

    def test_returns_empty_list_when_no_match(self, transcript_dir):
        results = search("xyz_no_match_xyz", transcript_dir)
        assert results == []

    def test_raises_when_dir_missing(self, tmp_path):
        missing = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            search("anything", missing)

    def test_regex_mode(self, transcript_dir):
        # Search for lines that start with a bold timestamp
        results = search(r"\*\*\[00:0[12]", transcript_dir, use_regex=True)
        assert len(results) >= 1

    def test_invalid_regex_raises(self, transcript_dir):
        with pytest.raises(re.error):
            search("[invalid", transcript_dir, use_regex=True)

    def test_max_results_respected(self, transcript_dir):
        # All files have several lines — max_results=1 should cap output
        results = search("00", transcript_dir, max_results=1)
        assert len(results) == 1

    def test_timestamp_extracted(self, transcript_dir):
        results = search("God Object", transcript_dir)
        assert len(results) == 1
        assert results[0].timestamp == "00:01:00"

    def test_no_timestamp_when_line_has_none(self, transcript_dir):
        results = search("Антипатерни", transcript_dir)
        # The heading line has no **[HH:MM:SS]** prefix
        heading_results = [r for r in results if r.timestamp is None]
        assert heading_results  # at least one result should have no timestamp

    def test_result_has_correct_title(self, transcript_dir):
        results = search("Dependency Injection", transcript_dir)
        assert any(r.title == "Dependency_Injection" for r in results)


# ---------------------------------------------------------------------------
# SearchResult.format()
# ---------------------------------------------------------------------------

class TestSearchResultFormat:
    def test_format_includes_title_and_timestamp(self):
        r = SearchResult(
            filepath  = Path("lectures/Test.md"),
            title     = "Test",
            line_no   = 42,
            timestamp = "00:05:30",
            snippet   = "Some matched text here.",
        )
        output = r.format()
        assert "Test" in output
        assert "00:05:30" in output
        assert "line 42" in output
        assert "Some matched text here." in output

    def test_format_without_timestamp(self):
        r = SearchResult(
            filepath  = Path("lectures/Test.md"),
            title     = "Test",
            line_no   = 1,
            timestamp = None,
            snippet   = "Heading line.",
        )
        output = r.format()
        assert "@" not in output  # timestamp anchor not shown
