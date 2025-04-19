# test_ttl.py
import asyncio
import time
from datetime import datetime
from ai_lab_tracker.firecrawl_adapter import fetch
from ai_lab_tracker.models import ChangeTracking

async def check_ttl(url: str, interval: int = 60, max_checks: int = 60):
    """
    Hit Firecrawl every `interval` seconds up to `max_checks` times,
    and report when it actually re-scrapes (i.e. changeStatus != 'same').
    """
    # First scrape → baseline
    r1 = await fetch(url, mode="GitDiff")
    ct1: ChangeTracking = r1.change_tracking
    t0 = ct1.previous_scrape_at or datetime.utcnow()
    print(f"[Baseline] previousScrapeAt = {t0.isoformat()}, changeStatus = {ct1.change_status!r}")

    # Subsequent scrapes
    for i in range(1, max_checks + 1):
        print(f"Sleeping {interval}s (check #{i}) …")
        time.sleep(interval)

        r2 = await fetch(url, mode="GitDiff")
        ct2: ChangeTracking = r2.change_tracking
        t1 = ct2.previous_scrape_at or t0
        status = ct2.change_status

        print(f"[Check #{i}] previousScrapeAt = {t1.isoformat()}, changeStatus = {status!r}")
        if status != "same":
            delta = (t1 - t0).total_seconds()
            print(f"\n🚀 Firecrawl finally re-scraped after ~{delta:.0f}s!")
            return

    print(f"\n⚠️ No re-scrape detected after {interval * max_checks}s (~{(interval*max_checks)/3600:.1f}h).")

if __name__ == "__main__":
    # Test against GitHub Zen endpoint
    TEST_URL = "https://api.github.com/zen"
    asyncio.run(check_ttl(TEST_URL, interval=300, max_checks=12))
