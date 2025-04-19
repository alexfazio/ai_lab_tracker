#!/usr/bin/env python3
"""
firecrawl_change_tracker.py
---------------------------

Track how https://www.whattimeisit.com changes over time using
Firecrawl’s change‑tracking format.

* Reads your API key from the FIRECRAWL_API_KEY env var (or first CLI arg).
* Requests both 'markdown' and 'changeTracking', as required.
* Prints the change‑tracking metadata on the first scrape.
* When run with --loop it keeps scraping every 60 s so you can see the
  changeStatus flip from "new" ➞ "changed"/"same" and inspect the diff.

Git‑diff mode is free; JSON mode costs 5 credits per scrape, so it’s
opt‑in via --json.

Usage:
  pip install firecrawl
  export FIRECRAWL_API_KEY=sk-...
  python firecrawl_change_tracker.py [--loop] [--json]

Author: you :-)
"""

from __future__ import annotations

import argparse
import os
import time
from pprint import pprint

from firecrawl import FirecrawlApp  # pip install firecrawl

URL = "https://www.whattimeisit.com"


def scrape(app: FirecrawlApp, include_json: bool = False) -> dict:
    """Scrape once and return the raw Firecrawl response dict."""
    return app.scrape_url(
        URL,
        {
            "formats": ["markdown", "changeTracking"],
            "changeTrackingOptions": {
                "modes": ["git-diff"] + (["json"] if include_json else [])
            },
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Firecrawl change‑tracking demo")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep scraping every 60 s so you can watch changes",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also request JSON mode (costs 5 credits/scrape)",
    )
    parser.add_argument(
        "api_key",
        nargs="?",
        default=os.getenv("FIRECRAWL_API_KEY"),
        help="Firecrawl API key (defaults to $FIRECRAWL_API_KEY)",
    )
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit(
            "No API key provided. Pass it as the first argument or set "
            "the FIRECRAWL_API_KEY environment variable."
        )

    app = FirecrawlApp(api_key=args.api_key)

    # --------------- first scrape ---------------
    result = scrape(app, include_json=args.json)
    ct = result.get("changeTracking", {})
    print("First scrape:")
    pprint(ct, compact=True, sort_dicts=False)

    # --------------- optional loop --------------
    if not args.loop:
        return

    print("\nLooping every 60 s – press Ctrl‑C to stop.\n")
    while True:
        time.sleep(60)
        result = scrape(app, include_json=args.json)
        ct = result.get("changeTracking", {})
        ts = ct.get("previousScrapeAt")
        status = ct.get("changeStatus")
        print(f"[{ts}] changeStatus = {status}")
        if "diff" in ct:
            print(ct["diff"]["text"])
        if args.json and "json" in ct:
            pprint(ct["json"], compact=True)
        print("-" * 80)


if __name__ == "__main__":
    main()
