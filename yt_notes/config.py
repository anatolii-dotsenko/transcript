"""
config.py
=========
Centralised configuration loaded from environment variables / .env file.
All application-wide constants live here so that other modules never
import ``os.environ`` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this file)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# ---------------------------------------------------------------------------
# Lecture catalogue
# ---------------------------------------------------------------------------
DEFAULT_LECTURES: dict[str, str] = {
    "Підходи до розробки програмного забезпечення": "https://www.youtube.com/watch?v=hysVHSlGJ7w",
    "Оцінка якості коду":                           "https://www.youtube.com/watch?v=yyz5NL2fGc8",
    "Тестування як інструмент розробки":            "https://www.youtube.com/watch?v=5K-4fCQMgck",
    "Спеціалізовані підвиди об'єктів":              "https://www.youtube.com/watch?v=qSj-9wusFd8",
    "Антипатерни":                                  "https://www.youtube.com/watch?v=WsUx7O2Ku5I",
    "Шаблони вищого рівня":                         "https://www.youtube.com/watch?v=v3F8amx_Lec",
    "ООП в контексті функціонального програмування":"https://www.youtube.com/watch?v=bVL1d4hrhWg",
    "Види та необхідність архітектури ПЗ":          "https://www.youtube.com/watch?v=g8g2DWPHsXw",
    "Архітектура та способи розгортання додатків":  "https://www.youtube.com/watch?v=caih5s_9BHY",
    "Передача інформації між компонентами":         "https://www.youtube.com/watch?v=Q0i0pPHFRTQ",
    "Створення застосунків з Dependency Injection":  "https://www.youtube.com/watch?v=7TQUpJJcucA",
    "Веб-розробка та її особливості":               "https://www.youtube.com/watch?v=IPxUrHotr68",
    "Види веб-додатків та підходи їх реалізації":   "https://www.youtube.com/watch?v=pKMhSoITatY",
    "Архітектура розповсюджених процесів":          "https://www.youtube.com/watch?v=ND4fkq0Lm5c",
}


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """
    Application-wide settings resolved from environment variables.

    Attributes:
        transcript_dir: Root folder where transcript ``.md`` files are stored.
        gemini_api_key: Google Gemini API key (empty string if not configured).
        log_level:      Python logging level name (e.g. ``"INFO"``).
        lang_priority:  Ordered list of BCP-47 language codes tried when
                        selecting a transcript track.
        delay_min:      Minimum seconds to sleep between transcript requests.
        delay_max:      Maximum seconds to sleep between transcript requests.
        max_retries:    How many times to retry a failed transcript fetch
                        before giving up.
        retry_base:     Base seconds for exponential back-off between retries.
    """

    transcript_dir: Path = field(
        default_factory=lambda: Path(os.getenv("TRANSCRIPT_DIR", "lectures"))
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "")
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    lang_priority: list[str] = field(
        default_factory=lambda: ["uk", "ru", "en"]
    )
    delay_min: float = 3.0
    delay_max: float = 8.0
    max_retries: int = 3
    retry_base: float = 5.0


# Module-level singleton — import this everywhere
settings = Settings()
