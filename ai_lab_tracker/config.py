"""Centralised configuration for ai_lab_tracker.

Loads all environment‑driven settings once and makes them available as
module‑level constants so that individual modules don't repeat
`os.getenv` logic.
"""

from __future__ import annotations

import os
from pathlib import Path

# =================================================================================================
# FIRECRAWL
# =================================================================================================

FIRECRAWL_API_KEY: str | None = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_RATE_LIMIT_PER_MINUTE: int = int(os.getenv("FIRECRAWL_RATE_LIMIT_PER_MINUTE", "5"))
RATE_WINDOW: float = 60.0  # seconds for sliding window

# =================================================================================================
# TELEGRAM
# =================================================================================================

TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_IDS: str = os.getenv("TELEGRAM_CHAT_IDS", "")

# Whether to forward logs to Telegram
TELEGRAM_SEND_LOGS: bool = os.getenv("TELEGRAM_SEND_LOGS", "false").lower() in {"1", "true", "yes"}

# =================================================================================================
# OPENAI
# =================================================================================================

OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

# =================================================================================================
# STATE DIRECTORY
# =================================================================================================

STATE_DIR: Path = Path(".state")
STATE_DIR.mkdir(exist_ok=True)

# =================================================================================================
# LOGGING
# =================================================================================================

_lvl = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
    "NOTSET": 0,
}.get(_lvl, 20)

# -----------------------------------------------------------------------------
# Load .env early so that settings are present even during top‑level imports.
# -----------------------------------------------------------------------------

_ENV_PATH = Path(".env")
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        if _line.strip() and not _line.lstrip().startswith("#") and "=" in _line:
            k, v = _line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip()) 
