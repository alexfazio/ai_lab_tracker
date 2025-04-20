"""AI Lab Tracker: periodically polls configured sources, crawls docs, and notifies changes."""

# Standard library imports
import asyncio
import hashlib
import json
import logging
import os
import pathlib
import time
from datetime import datetime
from typing import Optional

# Local application imports
from .firecrawl_adapter import crawl_and_fetch, fetch
from .models import FirecrawlResult, SourceConfig, ChangeTracking, Diff
from .notifier import TelegramNotifier
from .source_loader import load_sources

# Optional Telegram logging
from .telegram_log_handler import TelegramLogHandler

async def run_once() -> None:
    """Run one iteration of the tracker: fetch all sources and notify changes."""
    # =================================================================================================
    # Global throttle
    # =================================================================================================
    # Base configuration prints to stdout
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # Optionally forward logs to Telegram if enabled
    send_logs = os.getenv("TELEGRAM_SEND_LOGS", "false").lower() in {"1", "true", "yes"}
    bot_token_env = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids_env = os.getenv("TELEGRAM_CHAT_IDS", "")
    if send_logs and bot_token_env and chat_ids_env:
        try:
            bot = TelegramNotifier(bot_token_env, chat_ids_env).bot  # reuse Bot instance
            chat_ids = TelegramNotifier(bot_token_env, chat_ids_env).chat_ids
            handler = TelegramLogHandler(bot, chat_ids)
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            logging.getLogger().addHandler(handler)
            logging.info("Telegram log handler activated for %s chat(s)", len(chat_ids))
        except Exception as exc:  # noqa: BLE001  (we swallow to not break main flow)
            logging.error("Failed to initialize TelegramLogHandler: %s", exc)

    # Global throttle: skip if last run was within 60 seconds
    state_dir = pathlib.Path('.state')
    state_dir.mkdir(exist_ok=True)
    run_state_file = state_dir / 'run_state.json'
    now = time.time()
    if run_state_file.exists():
        rs = json.loads(run_state_file.read_text())
        last = rs.get('last_run', 0)
        if now - last < 60:
            logging.info("Skipping run: last run was %.0f seconds ago", now - last)
            return
    # record run timestamp
    run_state_file.write_text(json.dumps({'last_run': now}))
    logging.info("Starting run_once")
    # =================================================================================================
    # Initialize notifier
    # =================================================================================================
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
    notifier = TelegramNotifier(bot_token, chat_ids)

    # =================================================================================================
    # Load sources and initialize doc rotation
    # =================================================================================================
    # Load all source configs
    sources = load_sources()
    # Identify doc sources for rotation
    doc_sources = [s for s in sources if s.labels and 'docs' in s.labels]
    # Initialize the cursor index for docs rotation
    doc_idx = 0
    # Determine which docs source to crawl this run (initialize cursor index)
    if doc_sources:
        state_dir = pathlib.Path('.state')
        state_dir.mkdir(exist_ok=True)
        cursor_file = state_dir / 'docs_cursor.json'
        last_run = 0.0
        # Load state if exists (cursor and last_run)
        if cursor_file.exists():
            data = json.loads(cursor_file.read_text())
            doc_idx = data.get('cursor', 0)
            last_run = data.get('last_run', 0)
        # Prepare next cursor (do not update last_run here)
        next_idx = (doc_idx + 1) % len(doc_sources)
    else:
        last_run = 0.0
        next_idx = 0
    # =================================================================================================
    # Fetch loop and notification
    # =================================================================================================
    notified_hashes = set()
    for source in sources:
        try:
            # Handle documentation sources via rotation
            if source.labels and 'docs' in source.labels:
                # Only attempt crawl for the selected docs source
                if doc_sources and source == doc_sources[doc_idx]:
                    docs_now = time.time()
                    # Calculate elapsed time; only skip if within past 60s (ignore negative values)
                    elapsed = docs_now - last_run
                    if elapsed >= 0 and elapsed < 60:
                        logging.info("Skipping docs crawl for %s; last run was %.0f seconds ago", source.url, elapsed)
                        continue
                    # Perform crawl and update last_run in state
                    results = await crawl_and_fetch(
                        source.url,
                        source.mode,
                        source.crawl_options,
                    )
                    # Persist updated cursor and last_run
                    state_dir = pathlib.Path('.state')
                    cursor_file = state_dir / 'docs_cursor.json'
                    cursor_file.write_text(json.dumps({'cursor': next_idx, 'last_run': docs_now}))
                else:
                    # Skip other docs sources this run
                    continue
            else:
                # Standard single-page fetch for non-doc sources
                single = await fetch(source.url, source.mode)
                results = [single]
        except Exception as e:
            logging.error("Error fetching %s: %s", source.url, e)
            continue
        for result in results:
            status = result.change_tracking.change_status
            if status in {"new", "changed", "removed"}:
                # Deduplicate by diff hash
                diff_obj = result.change_tracking.diff
                diff_text = diff_obj.text if diff_obj and diff_obj.text else ""
                diff_hash = hashlib.sha256(diff_text.encode()).hexdigest()
                if diff_hash in notified_hashes:
                    logging.info("Skipping duplicate diff for %s (%s)", source.name, result.url)
                    continue
                notified_hashes.add(diff_hash)
                logging.info("Notifying for %s: %s (%s)", source.name, status, result.url)
                await notifier.send(result, source)
    logging.info("run_once completed")
