# test_firecrawl.py
import asyncio
import time
from ai_lab_tracker.firecrawl_adapter import fetch
from ai_lab_tracker.notifier import TelegramNotifier
from ai_lab_tracker.models import SourceConfig
from ai_lab_tracker.firecrawl_adapter import RateLimitExceeded
from aiohttp import ClientError

async def main():
    # Use HTTPBin UUID endpoint for dynamic JSON data
    url = "http://httpbin.org/uuid"
    # Baseline fetch in JsonDiff mode
    print("Fetching baseline (A)...")
    r1 = await fetch(url, mode="JsonDiff")
    d1 = r1.change_tracking.diff
    print("Baseline diff JSON:", d1.json_data if d1 else "(baseline)")

    # Loop until a new UUID appears (max 5 attempts)
    for attempt in range(1, 6):
        time.sleep(10)
        print(f"Attempt {attempt}: fetching snapshot B")
        try:
            r2 = await fetch(url, mode="JsonDiff")
        except asyncio.TimeoutError:
            print("Fetch timed out; retrying...")
            continue
        except RateLimitExceeded as e:
            print("Rate limited; retrying after delay...", e)
            time.sleep(5)
            continue
        except ClientError as e:
            print("HTTP client error; retrying...", e)
            continue
        except Exception as e:
            print("Unexpected error; retrying...", e)
            continue
        diff = r2.change_tracking.diff
        print("Diff JSON data:", diff.json_data if diff else "(no diff)")
        if diff and diff.json_data:
            print("Change detected JSON:", diff.json_data)
            # Send Telegram notification
            notifier = TelegramNotifier()
            src = SourceConfig(
                name="GitHubZen", url=url, mode="JsonDiff", labels=["test"]
            )
            print("Sending Telegram notification...")
            await notifier.send(r2, src)
            return
        print("No change yet; retrying...")
    print("No change detected after 5 attempts.")

if __name__ == "__main__":
    asyncio.run(main()) 
