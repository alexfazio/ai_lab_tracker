import asyncio
import time
from ai_lab_tracker.firecrawl_adapter import fetch
async def main():
    r1=await fetch("https://news.ycombinator.com","GitDiff")
    print("1st diff:", r1.change_tracking.diff)
    time.sleep(60)
    r2=await fetch("https://news.ycombinator.com","GitDiff")
    print("2nd diff:", r2.change_tracking.diff)
asyncio.run(main())
