import asyncio
import time
from ai_lab_tracker.firecrawl_adapter import fetch

async def main():
    url = 'http://numbersapi.com/random/math?json'
    r1 = await fetch(url, mode='JsonDiff')
    d1 = r1.change_tracking.diff
    print('1st JSON diff:', d1.json_data if d1 else '(baseline)')
    time.sleep(2)
    r2 = await fetch(url, mode='JsonDiff')
    d2 = r2.change_tracking.diff
    print('2nd JSON diff:', d2.json_data if d2 else '(no change)')

if __name__ == '__main__': asyncio.run(main())
