"""Telegram notifier for FirecrawlResult change events."""

import asyncio
import os
from pathlib import Path
from typing import List, Union, Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter

from .models import FirecrawlResult, SourceConfig

# =================================================================================================
# ENVIRONMENT LOADING
# =================================================================================================

env_path = Path('.env')
if env_path.exists():
    with env_path.open() as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

# =================================================================================================
# NOTIFIER CLASS
# =================================================================================================


class TelegramNotifier:
    """Sends FirecrawlResult change diffs to Telegram chats."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_ids: Union[str, List[str]] = ""
    ) -> None:
        """Initialize the notifier with a bot token and chat IDs.

        Args:
            bot_token: Telegram bot token or fallback to TELEGRAM_BOT_TOKEN env var.
            chat_ids: Comma-separated string or list of chat IDs, or fallback to TELEGRAM_CHAT_IDS.
        """
        token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        raw_chats = chat_ids or os.getenv("TELEGRAM_CHAT_IDS", "")
        if not raw_chats:
            raise ValueError("TELEGRAM_CHAT_IDS environment variable is required")

        self.bot: Bot = Bot(token=token)

        # Parse chat IDs into list[int]
        chats: List[str]
        if isinstance(raw_chats, str):
            chats = [cid.strip() for cid in raw_chats.split(",") if cid.strip()]
        else:
            chats = raw_chats
        self.chat_ids: List[int] = [int(cid) for cid in chats]

    async def send(
        self,
        result: FirecrawlResult,
        source: SourceConfig
    ) -> None:
        """Send a change diff message to all configured chats.

        Args:
            result: The FirecrawlResult containing change_tracking.diff.
            source: The SourceConfig for the result.
        """
        diff_obj = result.change_tracking.diff
        diff_text = diff_obj.text if diff_obj and diff_obj.text else None
        if not diff_text:
            # Nothing to send
            return

        title = source.name
        url = str(source.url)
        message = f"⚡ *{title}*\n{url}\n\n```diff\n{diff_text}```"
        button = [[InlineKeyboardButton("View page", url=url)]]
        markup = InlineKeyboardMarkup(button)

        for chat_id in self.chat_ids:
            sent = False
            while not sent:
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode="Markdown",
                        reply_markup=markup,
                    )
                    sent = True
                except RetryAfter as exc:
                    # Respect rate limit
                    await asyncio.sleep(exc.retry_after)
