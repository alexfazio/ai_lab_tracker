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
        # Generate a one‑sentence summary via OpenAI if API key available
        # ------------------------------------------------------------------

        async def _openai_summary(diff_markdown: str) -> str | None:  # noqa: D401
            """Return one‑sentence summary using OpenAI o4‑mini if configured."""
            if not os.getenv("OPENAI_API_KEY", ""):
                return None
            # Trim diff to reasonable length (o4‑mini context ~8k)
            snippet = diff_markdown[:4000]
            prompt = (
                "You will be given a Git‑style diff from a web page scrape."
                " Summarise *in one short sentence* the main change that happened."
                " Do not mention the diff itself."
            )
            try:
                import openai

                response = await openai.ChatCompletion.acreate(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": snippet},
                    ],
                    max_tokens=60,
                    temperature=0.3,
                )
                return response.choices[0].message.content.strip()
            except Exception as exc:  # noqa: BLE001
                # Log but fallback gracefully
                import logging

                logging.debug("OpenAI summary failed: %s", exc)
                return None

        # ------------------------------------------------------------------
        # Local heuristic fallback summary builder
        # ------------------------------------------------------------------
        def _summarise(git_diff: str, max_lines: int = 20) -> str:
            """Convert a Git‑diff into a short, human‑readable changelog.

            We keep both added (🆕) and removed (🗑️) lines so the reader can see
            what appeared and disappeared. Lines are cleaned to remove markdown
            noise and truncated for brevity.
            """

            additions: list[str] = []
            deletions: list[str] = []
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
                # Skip headers and context lines
                if line.startswith(("+++", "---", "@@")):
                    continue
                if not line.startswith(("+", "-")):
                    continue

                txt = _clean(line[1:])
                if not txt or any(p.search(txt) for p in noise_patterns):
                    continue

                if line.startswith("+"):
                    additions.append(txt)
                else:
                    deletions.append(txt)

            # Build final list interleaving adds/removals up to max_lines
            summary_lines: list[str] = []
            for add in additions:
                summary_lines.append("🆕 " + add)
                if len(summary_lines) >= max_lines:
                    break
            for rem in deletions:
                if len(summary_lines) >= max_lines:
                    break
                summary_lines.append("🗑️ " + rem)

            if len(summary_lines) < (len(additions) + len(deletions)):
                summary_lines.append("… (truncated) …")

            # Fallback
            return "\n".join(summary_lines) if summary_lines else git_diff

        summary = await _openai_summary(diff_text)
        if not summary:
            summary = _summarise(diff_text)

        title = source.name
        url = str(source.url)
        message = f"⚡ *{title}*\n{url}\n\n{summary}"
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
