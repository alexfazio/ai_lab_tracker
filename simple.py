"""
track_zen.py ― Tiny demo of Firecrawl Change Tracking with https://www.whattimeisit.com

Prerequisites
-------------
pip install firecrawl python-dotenv   # official SDK and .env support
export FIRECRAWL_API_KEY=fc-...       # your Firecrawl key (or place in .env)

Usage
-----
python track_zen.py            # run once
python track_zen.py --watch 60 # re‑scrape every 60 seconds
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
import requests

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("Please `pip install python-dotenv` for .env support.")
try:
    # documented import path (re‑exported at top level too)
    from firecrawl.firecrawl import FirecrawlApp
except ImportError:
    sys.exit("Please `pip install firecrawl` before running this script.")

# ---------------------------------------------------------------------------

load_dotenv()  # Load environment variables from .env

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    sys.exit("Set the FIRECRAWL_API_KEY environment variable first.")

# Use a page that returns a random dad joke on each request (server‑rendered HTML)
# This avoids TLS issues seen with previous endpoints and guarantees content changes.
CLOCK_URL = "https://icanhazdadjoke.com/"

# Firecrawl parameters: request both markdown and change‑tracking formats
SCRAPE_PARAMS = {
    "formats": ["markdown", "changeTracking"],
    "changeTrackingOptions": {"modes": ["git-diff"]},
}


def now() -> str:
    """Current UTC time in ISO‑8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def firecrawl_raw_scrape(url: str, params: dict[str, object], api_key: str) -> dict:
    """Directly call Firecrawl REST API, returning raw JSON with changeTracking."""
    api_url = "https://api.firecrawl.dev/v1/scrape"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"url": url, **params}
    response = requests.post(api_url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    data = response.json()
    if not data.get("success"):
        raise RuntimeError(f"Firecrawl error: {data}")
    return data["data"]


def scrape_once(app: FirecrawlApp) -> str:
    """
    Scrape the target URL with change‑tracking enabled and print any diff.

    Returns the Firecrawl changeStatus ('new' | 'same' | 'changed' | 'removed').
    """
    try:
        # SDK call first (may drop changeTracking)
        result = app.scrape_url(
            CLOCK_URL,
            formats=["markdown", "changeTracking"],
            changeTrackingOptions={"modes": ["git-diff"]},
        )
        # If changeTracking missing, fallback to raw REST call
        if hasattr(result, "dict") and "changeTracking" not in result.dict():
            logging.debug("SDK response missing changeTracking – falling back to raw REST call")
            raw = firecrawl_raw_scrape(CLOCK_URL, SCRAPE_PARAMS, API_KEY)
            result = raw  # overwrite with raw dict containing changeTracking
    except TypeError:
        # In case SDK signature complains again, use raw REST call directly
        logging.debug("SDK call failed, using raw REST call")
        result = firecrawl_raw_scrape(CLOCK_URL, SCRAPE_PARAMS, API_KEY)
    except requests.exceptions.HTTPError as http_err:  # type: ignore[attr-defined]
        resp = http_err.response  # type: ignore[attr-defined]
        if resp is not None:
            logging.error("HTTP %s error. Response text: %s", resp.status_code, resp.text)
        logging.exception("HTTPError during scrape_url call")
        return "error"
    except Exception:
        logging.exception("Error during scrape_url call")
        return "error"

    # Check if result is a dictionary or an object with attributes
    if hasattr(result, '__getitem__'):
        # Dictionary-like access
        change = result.get("changeTracking")
    elif hasattr(result, 'changeTracking'):
        # Object attribute access
        change = result.changeTracking
    else:
        # Try to convert to dict if it has a method for that
        try:
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
                change = result_dict.get("changeTracking")
            elif hasattr(result, '__dict__'):
                result_dict = result.__dict__
                change = result_dict.get("changeTracking")
            else:
                change = None
        except Exception:
            logging.exception("Error accessing changeTracking data")
            change = None

    if not change:
        print(f"[{now()}] No changeTracking data found in Firecrawl response.")
        return "unknown"

    # Handle both dictionary and object access for status and previousScrapeAt
    if hasattr(change, '__getitem__'):
        status = change.get("changeStatus", "unknown")
        previous = change.get("previousScrapeAt")
        diff = change.get("diff")
    else:
        status = getattr(change, "changeStatus", "unknown")
        previous = getattr(change, "previousScrapeAt", None)
        diff = getattr(change, "diff", None)

    print(f"[{now()}] changeStatus={status} previousScrapeAt={previous}")

    if status == "changed" and diff:
        print("---- Git‑Diff ----")
        # Handle both dictionary and object access for diff text
        if hasattr(diff, '__getitem__'):
            diff_text = diff.get("text", "<no diff text>")
        else:
            diff_text = getattr(diff, "text", "<no diff text>")
        print(diff_text)
        print("------------------")

    if hasattr(result, 'dict'):
        logging.debug("Result dict: %s", result.dict(exclude_none=True))
    else:
        logging.debug("Raw result: %r", result)

    if not change:
        if isinstance(result, dict):
            logging.debug("Top-level keys in result: %s", list(result.keys()))
        elif hasattr(result, '__dict__'):
            logging.debug("Top-level attributes in result: %s", list(result.__dict__.keys()))

    return status


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Track website changes using Firecrawl Change Tracking"
    )
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Poll the URL every SECONDS seconds (Ctrl‑C to quit)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    app = FirecrawlApp(api_key=API_KEY)

    if args.watch:
        try:
            while True:
                scrape_once(app)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        scrape_once(app)


if __name__ == "__main__":
    main()
