"""Adapter for the Firecrawl change-tracking API via AsyncFirecrawlApp."""

import importlib
import os
import re
import asyncio
import logging
from time import monotonic
from collections import deque
from typing import Optional, List

from .models import FirecrawlResult, CrawlOptions
from . import config

# =================================================================================================
# CLIENT INITIALIZATION
# =================================================================================================

# Dynamic import of AsyncFirecrawlApp to avoid static import errors
_firecrawl_mod = importlib.import_module("firecrawl.firecrawl")
AsyncFirecrawlApp = getattr(_firecrawl_mod, "AsyncFirecrawlApp")

# Validate presence of FIRECRAWL_API_KEY environment variable
api_key = config.FIRECRAWL_API_KEY
if not api_key:
    raise ValueError("FIRECRAWL_API_KEY environment variable is not set")

APP: AsyncFirecrawlApp = AsyncFirecrawlApp(api_key=api_key)

# =================================================================================================
# RATE LIMIT CONFIGURATION
# =================================================================================================
# Number of allowed Firecrawl requests per sliding 60-second window (free tier defaults ~5)
_RATE_LIMIT_PER_MINUTE = config.FIRECRAWL_RATE_LIMIT_PER_MINUTE
# Sliding window duration in seconds
_RATE_WINDOW = config.RATE_WINDOW
# Deque to hold timestamps of the last calls
_call_timestamps: deque[float] = deque()

class RateLimitExceeded(Exception):
    """Raised when exceeding allowed Firecrawl calls per RATE_WINDOW."""
    pass

async def _enforce_rate_limit() -> None:
    """Block until the request is allowed under the sliding‑window limit."""
    while True:
        now = monotonic()
        # Discard old timestamps outside the window
        while _call_timestamps and now - _call_timestamps[0] > _RATE_WINDOW:
            _call_timestamps.popleft()

        if len(_call_timestamps) < _RATE_LIMIT_PER_MINUTE:
            _call_timestamps.append(now)
            return  # allowed immediately

        # Need to wait until the earliest call falls out of window
        wait_time = _RATE_WINDOW - (now - _call_timestamps[0]) + 0.05
        await asyncio.sleep(wait_time)

# =================================================================================================
# INTERNAL RATE REPLAY HELPER
# =================================================================================================
async def _post_with_retry(url: str, payload: dict, headers: dict, max_retries: int = 2) -> dict:
    """
    Perform an async POST with throttle and limited 429 retry support.
    """
    attempts = 0
    while True:
        try:
            await _enforce_rate_limit()
            return await APP._async_post_request(url, payload, headers)
        except RateLimitExceeded:
            # This branch should rarely happen now, but keep fallback
            await asyncio.sleep(_RATE_WINDOW)
            attempts += 1
            continue
        except Exception as e:
            msg = str(e).lower()
            if attempts < max_retries and ('rate limit' in msg or 'retry after' in msg):
                m = re.search(r'retry after (\d+)s', msg)
                wait = int(m.group(1)) if m else 60
                logging.warning("Firecrawl backend rate limited; retrying after %s seconds", wait)
                await asyncio.sleep(wait)
                attempts += 1
                continue
            raise

# =================================================================================================
# FETCH FUNCTION
# =================================================================================================

async def fetch(url: str, mode: str = "GitDiff") -> FirecrawlResult:
    """Fetch a URL using Firecrawl's change-tracking API.

    Args:
        url: The URL to fetch.
        mode: The change-tracking format (e.g., 'GitDiff').

    Returns:
        A validated FirecrawlResult instance.
    """
    # Ensure URL is serializable
    url_str = str(url)
    # Canonicalise mode to Firecrawl enum ("git-diff" | "json")
    mode_value = mode.lower()
    if mode_value in {"gitdiff", "git-diff"}:
        mode_value = "git-diff"
    elif mode_value == "json":
        mode_value = "json"
    # Build request parameters for change tracking
    endpoint = "/v1/scrape"
    headers = APP._prepare_headers()
    # Request markdown + changeTracking and pass mode in options
    payload = {
        "url": url_str,
        "formats": ["markdown", "changeTracking"],
        "changeTrackingOptions": {"modes": [mode_value]}
    }
    # POST with retry on rate limit
    response = await _post_with_retry(f"{APP.api_url}{endpoint}", payload, headers)
    data = response.get("data")
    if not data:
        raise ValueError("No data returned in Firecrawl response")
    # Ensure the URL is present for model validation
    data["url"] = url_str
    # Ensure changeTracking key exists to satisfy model; Firecrawl sometimes omits
    if "changeTracking" not in data:
        data["changeTracking"] = {
            "previousScrapeAt": None,
            "changeStatus": "unknown",
            "visibility": "public",
        }
    # Validate and return high-level result model
    return FirecrawlResult.model_validate(data)

# Add support for crawling documentation sources with change-tracking
async def crawl_and_fetch(
    url: str,
    mode: str = "GitDiff",
    crawl_options: Optional[CrawlOptions] = None,
) -> List[FirecrawlResult]:
    """
    Crawl a documentation site with change-tracking and return results for each page.
    """
    url_str = str(url)
    endpoint = "/v1/crawl"
    headers = APP._prepare_headers()
    # Build payload including optional crawlOptions
    payload: dict = {"url": url_str}
    if crawl_options:
        payload.update(crawl_options.model_dump(by_alias=True, exclude_none=True))
    # Canonicalise mode to Firecrawl enum
    mode_value = mode.lower()
    if mode_value in {"gitdiff", "git-diff"}:
        mode_value = "git-diff"
    elif mode_value == "json":
        mode_value = "json"

    # Include changeTrackingOptions inside scrapeOptions
    payload["scrapeOptions"] = {
        "formats": ["markdown", "changeTracking"],
        "changeTrackingOptions": {"modes": [mode_value]},
    }

    # POST with retry on rate limit
    response = await _post_with_retry(f"{APP.api_url}{endpoint}", payload, headers)
    items = response.get("data") or []
    results: List[FirecrawlResult] = []
    for item in items:
        item_url = item.get("url", url_str)
        item["url"] = item_url
        if "changeTracking" not in item:
            item["changeTracking"] = {
                "previousScrapeAt": None,
                "changeStatus": "unknown",
                "visibility": "public",
            }
        results.append(FirecrawlResult.model_validate(item))
    return results
