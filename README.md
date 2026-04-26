# YT Notes — Local Video Transcript Manager

A production-ready CLI tool that downloads, normalises, and full-text-searches
YouTube lecture transcripts, with optional AI summarisation via Google Gemini.

## Features

- ✅ Batch transcript download with resume support (skip already-downloaded files)
- ✅ Rate-limit-safe random delays + exponential back-off on failures
- ✅ Language priority list (uk → ru → en → first available)
- ✅ Clean `.md` output with optional timestamp anchors for in-video navigation
- ✅ Full-text search: returns filename + timestamp + surrounding context
- ✅ Gemini AI summarisation (free tier for students)
- ✅ Structured logging (console + rotating file)
- ✅ Fully typed, PEP 8-compliant, all docstrings in English

## Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in GEMINI_API_KEY (optional)
```

## Quick Start

```bash
# Download all transcripts from the built-in lecture list
python -m yt_notes download

# Download from a custom JSON file
python -m yt_notes download --source my_links.json

# Search across all saved transcripts
python -m yt_notes search "dependency injection"

# Summarise a single transcript with Gemini
python -m yt_notes summarise "lectures/Антипатерни.md"
```

## Project Layout

```
yt_notes/
├── yt_notes/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point  (python -m yt_notes)
│   ├── config.py            # Settings / constants
│   ├── downloader.py        # Transcript fetching logic
│   ├── formatter.py         # Raw transcript → clean Markdown
│   ├── searcher.py          # Full-text search engine
│   ├── summariser.py        # Gemini AI integration
│   └── logger.py            # Logging setup
├── tests/
│   ├── test_formatter.py
│   ├── test_searcher.py
│   └── test_downloader.py
├── .env.example
├── requirements.txt
└── README.md
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | No | Google Gemini API key for AI summarisation |
| `TRANSCRIPT_DIR` | No | Output folder (default: `lectures`) |
| `LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` (default: `INFO`) |
