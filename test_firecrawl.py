# test_firecrawl.py
import os
import asyncio
import time
from ai_lab_tracker.firecrawl_adapter import fetch
from ai_lab_tracker.notifier import TelegramNotifier
from ai_lab_tracker.models import SourceConfig
from ai_lab_tracker.firecrawl_adapter import RateLimitExceeded
from aiohttp import ClientError

"""
End-to-end Firecrawl test script against a dynamic HTML endpoint.
Set the environment variable DYNAMIC_URL to a public URL (e.g., via ngrok).
"""

async def main():
    # Use the provided dynamic URL (or fallback)
    url = os.getenv("DYNAMIC_URL", "http://localhost:5000")
    print(f"Using dynamic URL: {url}")

    # Baseline fetch (A)
    print("Fetching baseline (A)...")
    r1 = await fetch(url, mode="GitDiff")
    d1 = r1.change_tracking.diff
    print("Baseline diff text:", d1.text if d1 and d1.text else "(baseline)")

    # Immediate second fetch (B) - NOTE: Likely hits Firecrawl cache!
    # Firecrawl's free/hobby tier cache TTL is very long (~17 hours in tests).
    # To see a real diff, run this script once, wait 17+ hours, then run again.
    # For rapid testing of logic, use local_diff.py to bypass Firecrawl.
    print("Fetching second snapshot (B) immediately...")
    try:
        r2 = await fetch(url, mode="GitDiff")
    except Exception as e:
        print(f"Error fetching second snapshot: {e}")
        return

    # Check for diff and notify if found
    diff = r2.change_tracking.diff
    print("Diff text from A->B:", diff.text if diff else "(no change - likely cached)")
    if diff and diff.text:
        print("Real change detected! Sending Telegram notification...")
        notifier = TelegramNotifier()
        src = SourceConfig(name="DynamicTest", url=url, mode="GitDiff", labels=["test"])
        await notifier.send(r2, src)
    else:
        print("No diff found. Run again after Firecrawl cache TTL (17+ hours) expires.")

if __name__ == "__main__":
    asyncio.run(main()) 
 