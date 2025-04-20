"""Logging handler that forwards log records to Telegram chats.

This module defines `TelegramLogHandler`, a custom `logging.Handler` subclass that
forwards formatted log messages to Telegram using the existing bot credentials.
It is **optional** and only activated if the `TELEGRAM_SEND_LOGS` environment
variable is set to a truthy value.
"""

from __future__ import annotations

import logging
from typing import List

from telegram import Bot

# Telegram limits messages to 4096 bytes; we stay below that to be safe.
_MAX_LEN = 4000


class TelegramLogHandler(logging.Handler):
    """A logging handler that forwards log records to Telegram chats.

    The handler is lightweight and synchronous – it sends each emitted log
    record directly via the provided :class:`telegram.Bot`. If your workload
    is very chatty you may prefer buffering, but for periodic GitHub Action
    jobs this simple approach is sufficient.
    """

    def __init__(self, bot: Bot, chat_ids: List[int], level: int = logging.INFO) -> None:  # noqa: D401,E501
        """Create a new handler.

        Args:
            bot: An **initialized** instance of :class:`telegram.Bot`.
            chat_ids: List of chat IDs that should receive log messages.
            level: Minimum log level that will be forwarded (default: INFO).
        """
        super().__init__(level)
        self._bot = bot
        self._chat_ids = chat_ids

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    async def _async_send(self, chat_id: int, text: str) -> None:  # noqa: D401
        """Coroutine that sends *text* to a single chat ID, splitting chunks."""
        start = 0
        end = len(text)
        while start < end:
            chunk = text[start : min(start + _MAX_LEN, end)]  # noqa: E203  (black slice)
            await self._bot.send_message(chat_id=chat_id, text=chunk)
            start += _MAX_LEN

    def _send(self, text: str) -> None:
        """Schedule asynchronous send tasks for all chats."""
        import asyncio

        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop; fall back to a new temporary loop (rare in GH Action)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        tasks = [self._async_send(cid, text) for cid in self._chat_ids]
        # Fire‑and‑forget: schedule tasks but don't block logging flow
        for t in tasks:
            asyncio.create_task(t)

    # ------------------------------------------------------------------
    # Overridden API
    # ------------------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        """Format *record* and forward it to Telegram."""
        try:
            # Avoid recursive logging by skipping records originating from the
            # telegram library itself.
            if record.name.startswith("telegram"):
                return
            msg = self.format(record)
            prefix = f"[{record.levelname}] "
            self._send(prefix + msg)
        except Exception:  # pylint: disable=broad-except
            # We intentionally swallow all exceptions to avoid interfering with
            # the main logging flow.
            self.handleError(record) 
