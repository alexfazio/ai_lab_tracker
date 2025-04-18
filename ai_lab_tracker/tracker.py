import os
import logging
import hashlib
import time
from .firecrawl_adapter import fetch, crawl_and_fetch
from .source_loader import load_sources
from .notifier import TelegramNotifier
from .models import SourceConfig, FirecrawlResult
import pathlib
import json
import asyncio

async def run_once() -> None:
    """Run one iteration of the tracker: fetch all sources and notify changes."""
    logging.basicConfig(level=logging.INFO)
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
    # Initialize notifier
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
    notifier = TelegramNotifier(bot_token, chat_ids)

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
    notified_hashes = set()
    for source in sources:
        try:
            # Handle documentation sources via rotation
            if source.labels and 'docs' in source.labels:
                # Only attempt crawl for the selected docs source
                if doc_sources and source == doc_sources[doc_idx]:
                    now = asyncio.get_event_loop().time()
                    # Skip if last_run was within past 60s
                    if now - last_run < 60:
                        logging.info("Skipping docs crawl for %s; last run was %.0f seconds ago", source.url, now - last_run)
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
                    cursor_file.write_text(json.dumps({'cursor': next_idx, 'last_run': now}))
                else:
                    # Skip other docs sources this run
                    continue
            else:
                # Standard single-page fetch for non-doc sources
                single = await fetch(source.url, source.mode)
                results = [single]
        except Exception as e:
            logging.error(f"Error fetching {source.url}: {e}")
            continue
        for result in results:
            status = result.change_tracking.change_status
            if status in {"new", "changed", "removed"}:
                # Deduplicate by diff hash
                diff_obj = result.change_tracking.diff
                diff_text = diff_obj.text if diff_obj and diff_obj.text else ""
                diff_hash = hashlib.sha256(diff_text.encode()).hexdigest()
                if diff_hash in notified_hashes:
                    logging.info(f"Skipping duplicate diff for {source.name} ({result.url})")
                    continue
                notified_hashes.add(diff_hash)
                logging.info(f"Notifying for {source.name}: {status} ({result.url})")
                await notifier.send(result, source)
    logging.info("run_once completed")
