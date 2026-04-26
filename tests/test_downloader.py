"""
tests/test_downloader.py
========================
Unit tests for yt_notes.downloader helper functions.

Network calls are never made — the YouTube API client is mocked via
``unittest.mock.patch``.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from yt_notes.downloader import (
    sanitise_filename,
    extract_video_id,
    load_source,
    download_transcripts,
)


# ---------------------------------------------------------------------------
# sanitise_filename
# ---------------------------------------------------------------------------

class TestSanitiseFilename:
    def test_replaces_colon(self):
        assert ":" not in sanitise_filename("Title: Subtitle")

    def test_replaces_slash(self):
        assert "/" not in sanitise_filename("A/B")

    def test_replaces_backslash(self):
        assert "\\" not in sanitise_filename("A\\B")

    def test_plain_name_unchanged(self):
        assert sanitise_filename("Антипатерни") == "Антипатерни"

    def test_multiple_forbidden_chars(self):
        result = sanitise_filename('file*name?"test"')
        for ch in ('*', '?', '"'):
            assert ch not in result


# ---------------------------------------------------------------------------
# extract_video_id
# ---------------------------------------------------------------------------

class TestExtractVideoId:
    def test_watch_url(self):
        assert extract_video_id("https://www.youtube.com/watch?v=hysVHSlGJ7w") == "hysVHSlGJ7w"

    def test_short_url(self):
        assert extract_video_id("https://youtu.be/hysVHSlGJ7w") == "hysVHSlGJ7w"

    def test_url_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=hysVHSlGJ7w&t=120s&list=PLxxx"
        assert extract_video_id(url) == "hysVHSlGJ7w"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Cannot extract"):
            extract_video_id("https://example.com/not-youtube")


# ---------------------------------------------------------------------------
# load_source
# ---------------------------------------------------------------------------

class TestLoadSource:
    def test_none_returns_default_lectures(self):
        result = load_source(None)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_valid_json_file(self, tmp_path):
        data = {"My Lecture": "https://www.youtube.com/watch?v=abc1234567X"}
        p = tmp_path / "links.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        result = load_source(p)
        assert result == data

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_source(tmp_path / "nonexistent.json")

    def test_non_dict_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps(["list", "not", "dict"]), encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a JSON object"):
            load_source(p)


# ---------------------------------------------------------------------------
# download_transcripts (mocked API)
# ---------------------------------------------------------------------------

FAKE_SEGMENTS = [
    {"start": 0.0,  "text": "Hello world."},
    {"start": 5.0,  "text": "This is a test transcript."},
]

class TestDownloadTranscripts:
    def _make_api_mock(self, segments=FAKE_SEGMENTS):
        """Return a mock YouTubeTranscriptApi that yields fake segments."""
        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = segments

        mock_list = MagicMock()
        mock_list.find_transcript.return_value = mock_transcript
        mock_list.__iter__ = MagicMock(return_value=iter([mock_transcript]))

        mock_api = MagicMock()
        mock_api.list.return_value = mock_list
        return mock_api

    @patch("yt_notes.downloader.YouTubeTranscriptApi")
    @patch("yt_notes.downloader.time.sleep")  # skip real delays
    def test_saves_file(self, _sleep, mock_cls, tmp_path):
        mock_cls.return_value = self._make_api_mock()
        video_dict = {"Test Lecture": "https://www.youtube.com/watch?v=abc1234567X"}

        summary = download_transcripts(video_dict, output_dir=tmp_path)

        assert summary["saved"] == ["Test Lecture"]
        assert (tmp_path / "Test Lecture.md").exists()

    @patch("yt_notes.downloader.YouTubeTranscriptApi")
    @patch("yt_notes.downloader.time.sleep")
    def test_skips_existing_file(self, _sleep, mock_cls, tmp_path):
        # Pre-create the file
        (tmp_path / "Test Lecture.md").write_text("already here", encoding="utf-8")
        mock_cls.return_value = self._make_api_mock()
        video_dict = {"Test Lecture": "https://www.youtube.com/watch?v=abc1234567X"}

        summary = download_transcripts(video_dict, output_dir=tmp_path)

        assert summary["skipped"] == ["Test Lecture"]
        assert summary["saved"] == []
        # API should NOT have been called since file already exists
        mock_cls.return_value.list.assert_not_called()

    @patch("yt_notes.downloader.YouTubeTranscriptApi")
    @patch("yt_notes.downloader.time.sleep")
    def test_records_failure_on_api_error(self, _sleep, mock_cls, tmp_path):
        mock_api = MagicMock()
        mock_api.list.side_effect = Exception("Network error")
        mock_cls.return_value = mock_api

        video_dict = {"Bad Video": "https://www.youtube.com/watch?v=abc1234567X"}
        summary = download_transcripts(video_dict, output_dir=tmp_path)

        assert "Bad Video" in summary["failed"]
        assert summary["saved"] == []

    @patch("yt_notes.downloader.YouTubeTranscriptApi")
    @patch("yt_notes.downloader.time.sleep")
    def test_output_dir_created_if_missing(self, _sleep, mock_cls, tmp_path):
        mock_cls.return_value = self._make_api_mock()
        new_dir = tmp_path / "new" / "nested"
        video_dict = {"Lecture": "https://www.youtube.com/watch?v=abc1234567X"}

        download_transcripts(video_dict, output_dir=new_dir)

        assert new_dir.exists()
