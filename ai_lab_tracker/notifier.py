"""Telegram notifier for FirecrawlResult change events."""

import asyncio
import os
from pathlib import Path
from typing import List, Union, Optional
import re

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

        # ------------------------------------------------------------------
        # Render a compact, human‑readable summary of the diff
        # ------------------------------------------------------------------
        def _summarise(git_diff: str, max_lines: int = 25) -> str:
            """Return a concise, human‑readable diff summary.

            Heuristics:
            • Show only *added* lines (green `+`) – these usually represent the
              latest state after change.
            • Strip noisy media tags and very long URLs.
            • Collapse multiple spaces and truncate long lines.
            """

            additions: list[str] = []
            noise_patterns = [
                re.compile(r"your browser does not support", re.I),
                re.compile(r"<iframe", re.I),
                re.compile(r"!\[.*?\]\(.*?\)"),  # markdown image
            ]

            link_re = re.compile(r"\[([^\]]+)\]\([^\)]+\)")

            def _markdown_to_text(text: str) -> str:
                """Convert simple markdown links/images to plain text titles."""
                # Strip images completely
                text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", "", text)
                # Convert links: [title](url) -> title
                return link_re.sub(r"\1", text)

            def _clean(txt: str) -> str:
                txt = _markdown_to_text(txt)
                # Remove leftover URLs in parentheses
                txt = re.sub(r"https?://[^ )]+", "", txt)
                # Remove pipes and redundant symbols
                txt = re.sub(r"\|", " ", txt)
                # Collapse whitespace and punctuation spacing
                txt = re.sub(r"\s+", " ", txt).strip(" -|\t")
                # Compact date/time by removing redundant words like 'ago'
                txt = re.sub(r"\b(ago|hide)\b", "", txt, flags=re.I)
                txt = re.sub(r"\s+", " ", txt).strip()
                # Truncate long lines
                if len(txt) > 100:
                    txt = txt[:97] + "…"
                return txt

            for line in git_diff.splitlines():
                # Skip headers
                if line.startswith(("+++", "---", "@@")):
                    continue
                if not line.startswith("+"):
                    continue  # only additions
                txt = _clean(line[1:])
                if not txt or any(p.search(txt) for p in noise_patterns):
                    continue
                if txt:
                    additions.append("• " + txt)
                if len(additions) >= max_lines:
                    additions.append("… (truncated) …")
                    break

            # Fallback to original diff if nothing survived cleaning
            return "\n".join(additions) if additions else git_diff

        pretty = _summarise(diff_text)

        title = source.name
        url = str(source.url)
        message = f"⚡ *{title}*\n{url}\n\n{pretty}"
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
