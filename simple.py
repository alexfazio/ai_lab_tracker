"""
track_zen.py ― Tiny demo of Firecrawl Change Tracking with https://api.github.com/zen

Prerequisites
-------------
pip install firecrawl python-dotenv  # official SDK and .env support
export FIRECRAWL_API_KEY=fc-...   # your Firecrawl key (or place in .env)

Usage
-----
python track_zen.py            # run once
python track_zen.py --watch 60 # re‑scrape every 60 seconds
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import logging
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except ImportError:
    sys.exit("Please `pip install python-dotenv` for .env support.")
try:
    from firecrawl import FirecrawlApp
except ImportError:
    sys.exit("Please `pip install firecrawl` before running this script.")

load_dotenv()  # Load environment variables from .env file

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    sys.exit("Set the FIRECRAWL_API_KEY environment variable first.")

# Use a clock website that changes frequently for testing
CLOCK_URL = "http://www.whattimeisit.com"


def scrape_once(app: FirecrawlApp) -> str:
    """
    Scrape the Clock URL with changeTracking enabled and print any diff.
    Returns the changeStatus ('new' | 'same' | 'changed' | 'removed').
    """
    scrape_params = {
        "formats": ["markdown", "changeTracking"],
        "changeTrackingOptions": {"modes": ["git-diff"]},
    }
    logging.info("Scraping URL: %s with params: %s", CLOCK_URL, scrape_params)
    try:
        result = app.scrape_url(
            CLOCK_URL,
            formats=scrape_params["formats"],
            changeTrackingOptions=scrape_params["changeTrackingOptions"],
        )
        logging.info("Received response: %r", result)
    except Exception as e:
        logging.exception("Error during scrape_url call")
        return "error"

    status = "unknown"
    previous_scrape_at = None
    if hasattr(result, "changeTracking") and result.changeTracking:
        ct = result.changeTracking
        status = ct.changeStatus if hasattr(ct, "changeStatus") else "unknown"
        previous_scrape_at = (
            ct.previousScrapeAt if hasattr(ct, "previousScrapeAt") else None
        )

        print(
            f"[{datetime.now(timezone.utc).isoformat()}] changeStatus={status} "
            f"previousScrapeAt={previous_scrape_at}"
        )

        # If the content changed and git‑diff mode is available, print the diff text
        if status == "changed" and hasattr(ct, "diff") and ct.diff:
            print("---- Git‑Diff ----")
            print(ct.diff.text if hasattr(ct.diff, "text") else "No diff text available.")
            print("------------------")
    else:
        # changeTracking attribute was missing from the response
        print(
            f"[{datetime.now(timezone.utc).isoformat()}] No changeTracking data found in Firecrawl response."
        )

    return status


def main() -> None:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(
        description="Track website changes using Firecrawl Change Tracking"
    )
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Poll the Zen URL every SECONDS seconds (Ctrl‑C to quit)",
    )
    args = parser.parse_args()

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
