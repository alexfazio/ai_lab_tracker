import asyncio,time
from ai_lab_tracker.firecrawl_adapter import fetch
async def main():
    url='http://www.random.org/integers/?num=1&min=1&max=100&col=1&base=10&format=html&rnd=new'
    r1=await fetch(url,'GitDiff')
    print('1st diff:', r1.change_tracking.diff)
    time.sleep(2)
    r2=await fetch(url,'GitDiff')
    print('2nd diff:', r2.change_tracking.diff)
if __name__=='__main__': import asyncio; asyncio.run(main())
