import asyncio, time
from ai_lab_tracker.firecrawl_adapter import fetch

async def main():
    url = "https://worldtimeapi.org/api/timezone/Etc/UTC"
    # First snapshot
    r1 = await fetch(url, "GitDiff")
    print("1st diff:", r1.change_tracking.diff)
    # Wait for the API to tick over
    time.sleep(5)
    # Second snapshot
    r2 = await fetch(url, "GitDiff")
    print("2nd diff:", r2.change_tracking.diff)

if __name__ == "__main__":
    asyncio.run(main())
