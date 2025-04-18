import asyncio
import time
from ai_lab_tracker.firecrawl_adapter import fetch

async def main():
    url="https://worldtimeapi.org/api/timezone/Etc/UTC"
    r1 = await fetch(url, mode="JsonDiff")
    print("1st JSON diff:", r1.change_tracking.diff.json_data if r1.change_tracking.diff else "(baseline)")
    time.sleep(5)
    r2 = await fetch(url, mode="JsonDiff")
    print("2nd JSON diff:", r2.change_tracking.diff.json_data if r2.change_tracking.diff else "(no change)")

if __name__=="__main__":
    asyncio.run(main())
