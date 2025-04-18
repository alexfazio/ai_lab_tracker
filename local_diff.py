# local_diff.py
import asyncio
import aiohttp
import difflib
import time

async def main():
    url = "http://numbersapi.com/random/math"
    async with aiohttp.ClientSession() as session:
        # First fetch
        resp1 = await session.get(url)
        old_text = await resp1.text()
        print("Old content:\n", old_text)

        # Wait for new content
        time.sleep(2)

        # Second fetch
        resp2 = await session.get(url)
        new_text = await resp2.text()
        print("New content:\n", new_text)

    # Compute unified diff
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile="old",
        tofile="new",
        lineterm=""
    )
    print("Diff:\n", ''.join(diff))

if __name__ == "__main__":
    asyncio.run(main()) 
