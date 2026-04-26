"""
tests/test_formatter.py
=======================
Unit tests for yt_notes.formatter.

All tests use synthetic data — no network calls or file I/O.
"""

import pytest
from yt_notes.formatter import (
    seconds_to_timestamp,
    format_transcript,
    _clean_text,
    _extract_segment,
)


# ---------------------------------------------------------------------------
# seconds_to_timestamp
# ---------------------------------------------------------------------------

class TestSecondsToTimestamp:
    def test_zero(self):
        assert seconds_to_timestamp(0) == "00:00:00"

    def test_under_one_minute(self):
        assert seconds_to_timestamp(45) == "00:00:45"

    def test_one_hour(self):
        assert seconds_to_timestamp(3600) == "01:00:00"

    def test_fractional_seconds_truncated(self):
        # Floats should be truncated, not rounded
        assert seconds_to_timestamp(135.9) == "00:02:15"

    def test_large_value(self):
        assert seconds_to_timestamp(7261) == "02:01:01"


# ---------------------------------------------------------------------------
# _clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_removes_music_tag(self):
        assert _clean_text("[Music]") == ""

    def test_removes_applause(self):
        assert _clean_text("[Applause] Great talk") == "Great talk"

    def test_removes_html_tags(self):
        assert _clean_text("<c>hello</c>") == "hello"

    def test_collapses_whitespace(self):
        assert _clean_text("  hello   world  ") == "hello world"

    def test_plain_text_unchanged(self):
        assert _clean_text("Design patterns") == "Design patterns"


# ---------------------------------------------------------------------------
# _extract_segment
# ---------------------------------------------------------------------------

class TestExtractSegment:
    def test_dict_segment(self):
        seg = {"start": 12.5, "text": "Hello world"}
        start, text = _extract_segment(seg)
        assert start == pytest.approx(12.5)
        assert text == "Hello world"

    def test_dict_missing_start_defaults_to_zero(self):
        seg = {"text": "No start key"}
        start, _ = _extract_segment(seg)
        assert start == pytest.approx(0.0)

    def test_object_segment(self):
        class FakeSegment:
            start = 30.0
            text  = "Object style"

        start, text = _extract_segment(FakeSegment())
        assert start == pytest.approx(30.0)
        assert text == "Object style"


# ---------------------------------------------------------------------------
# format_transcript
# ---------------------------------------------------------------------------

SAMPLE_SEGMENTS = [
    {"start": 0.0,   "text": "Welcome to the lecture."},
    {"start": 5.0,   "text": "Today we discuss design patterns."},
    {"start": 10.0,  "text": "[Music]"},                   # noise — should be dropped
    {"start": 15.0,  "text": "The first pattern is Singleton."},
]


class TestFormatTranscript:
    def test_raises_on_empty_segments(self):
        with pytest.raises(ValueError, match="No transcript segments"):
            format_transcript([], title="Test", url="https://youtube.com/watch?v=abc")

    def test_header_contains_title(self):
        md = format_transcript(SAMPLE_SEGMENTS, title="My Lecture", url="https://example.com")
        assert "# My Lecture" in md

    def test_header_contains_url(self):
        url = "https://www.youtube.com/watch?v=abc123"
        md  = format_transcript(SAMPLE_SEGMENTS, title="T", url=url)
        assert url in md

    def test_timestamps_present_by_default(self):
        md = format_transcript(SAMPLE_SEGMENTS, title="T", url="u")
        assert "**[00:00:00]**" in md
        assert "**[00:00:05]**" in md

    def test_noise_segment_excluded(self):
        md = format_transcript(SAMPLE_SEGMENTS, title="T", url="u")
        # The [Music] segment should produce no output line
        assert "[Music]" not in md

    def test_no_timestamps_mode(self):
        md = format_transcript(SAMPLE_SEGMENTS, title="T", url="u", keep_timestamps=False)
        assert "**[" not in md
        assert "Welcome to the lecture" in md
