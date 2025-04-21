"""Telegram notifier for FirecrawlResult change events."""

import asyncio
import os
from pathlib import Path
from typing import List, Union, Optional

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter

from .models import FirecrawlResult, SourceConfig
from ai_lab_tracker.agent_evaluator import evaluate_diff  # local import to avoid startup cost

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

        # ---------------------------------------------------------------
        # Use OpenAI Agent to decide relevance & generate summary
        # ---------------------------------------------------------------
        try:
            agent_out = await evaluate_diff(diff_text)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.error("Agent evaluation failed for %s: %s", source.name, exc)
            return  # mandatory agent – skip notification

        if not agent_out.get("relevant"):
            # Not news‑worthy; do not notify
            return

        summary: str = agent_out.get("summary", "") or "(no summary)"

        title = source.name
        url = str(source.url)

        # Dynamically trim diff so the final message fits Telegram's 4096‑char limit.
        preamble = f"⚡ *{title}*\n{url}\n\n{summary}\n\n```diff\n"
        footer = "```"
        max_total = 4090  # small buffer below hard limit

        remaining = max_total - len(preamble) - len(footer)
        if remaining < 0:
            # summary itself is too long → truncate aggressively
            summary = summary[:300] + "…"
            preamble = f"⚡ *{title}*\n{url}\n\n{summary}\n\n```diff\n"
            remaining = max_total - len(preamble) - len(footer)

        diff_snippet = diff_text
        if len(diff_snippet) > remaining:
            diff_snippet = diff_snippet[: remaining - 1] + "…"

        message = preamble + diff_snippet + footer
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
