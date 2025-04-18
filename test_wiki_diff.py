# test_wiki_diff.py
import asyncio
import time
from ai_lab_tracker.firecrawl_adapter import fetch

async def main():
    url = "https://en.wikipedia.org/wiki/Special:Random"
    # First snapshot (baseline loads random article A)
    r1 = await fetch(url, mode="GitDiff")
    d1 = r1.change_tracking.diff
    print("1st Git diff (random article A):", '(baseline)' if not d1 else d1.text[:200])

    # Slight pause to ensure Special:Random returns a new article B
    time.sleep(2)

    # Second snapshot (random article B), diff against A
    r2 = await fetch(url, mode="GitDiff")
    d2 = r2.change_tracking.diff
    print("2nd Git diff (diff from A→B):", d2.text[:200] if d2 else '(no change)')

if __name__ == "__main__":
    asyncio.run(main()) 
