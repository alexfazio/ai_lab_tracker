from __future__ import annotations

"""Utility to decide whether a diff is news‑worthy using the OpenAI Agents SDK.

The agent returns a structured JSON:
    {
        "relevant": bool,
        "summary": str
    }

If the call fails for *any* reason we propagate the exception so the caller can
fallback or skip the notification.
"""

# =================================================================================================
# SECTION: Imports & setup
# =================================================================================================

import asyncio
import json
import logging
from typing import Any, Dict
import re

from ai_lab_tracker import config

try:
    from agents import Agent, Runner
except ImportError as exc:  # pragma: no cover  # noqa: D401
    raise ImportError(
        "openai‑agents not installed. Add 'openai-agents' to your dependencies."
    ) from exc

# =================================================================================================
# SECTION: Agent factory
# =================================================================================================

def _build_agent(model: str | None = None) -> Agent:  # noqa: D401
    """Return a configured Agent instance.

    The agent receives a git‑style diff (string) and must decide whether the
    change is interesting for AI‑news tracking. It outputs a JSON dict with the
    expected schema.
    """

    # Use provided model or fallback to env/default.
    model_name = model or config.OPENAI_MODEL

    SCHEMA_JSON = json.dumps(
        {
            "type": "object",
            "properties": {
                "relevant": {"type": "boolean"},
                "summary": {"type": "string"},
            },
            "required": ["relevant", "summary"],
        }
    )

    instructions = (
        "You are an expert news triage assistant focused on AI research, "
        "foundation models, and developer platform updates. "
        "You are given a *git‑style markdown diff* that shows changes on a web "
        "page (docs, blog, GitHub repo list, etc.).\n\n"
        "Your job:\n"
        "1. Analyse whether the diff contains *concrete, user‑relevant news* such "
        "as: a new model name, new API endpoint, release notes, policy changes, "
        "benchmark results, new GitHub repo, etc.\n"
        "   • Pure formatting tweaks, typo fixes, or auto‑generated timestamp "
        "     changes are NOT relevant.\n"
        "2. If relevant, produce a concise summary (1‑3 bullet points, prefix each "
        "   with '•'). Mention specific nouns/numbers.\n\n"
        "Return your answer as JSON matching this exact schema (no additional keys):\n"
        f"```json\n{SCHEMA_JSON}\n```"
    )

    return Agent(name="AI‑News‑Triage", instructions=instructions, model=model_name)

# =================================================================================================
# SECTION: Public helper
# =================================================================================================

aSYNC_LOCK: asyncio.Lock | None = None

def _get_lock() -> asyncio.Lock:  # noqa: D401
    """Return a module‑level asyncio.Lock to serialize API calls."""
    global aSYNC_LOCK  # noqa: PLW0603
    if aSYNC_LOCK is None:
        aSYNC_LOCK = asyncio.Lock()
    return aSYNC_LOCK


async def evaluate_diff(diff_markdown: str) -> Dict[str, Any]:  # noqa: D401
    """Return {"relevant": bool, "summary": str} decided by the agent."""

    agent = _build_agent()
    lock = _get_lock()
    async with lock:  # simple global serialization to avoid rate spikes
        result = await Runner.run(agent, input=diff_markdown)

    # Runner returns an object with `.final_output` which should be JSON
    output_raw: str = result.final_output if hasattr(result, "final_output") else str(result)
    cleaned = output_raw.strip()
    if cleaned.startswith("```"):
        # Remove ```json or ``` fencing (language tag optional)
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"```$", "", cleaned.strip())
    try:
        parsed: Dict[str, Any] = json.loads(cleaned)
        # Basic sanity validation
        if not isinstance(parsed.get("relevant"), bool) or not isinstance(parsed.get("summary"), str):
            raise ValueError("Agent returned invalid schema")
        return parsed
    except Exception as exc:  # noqa: BLE001
        logging.error("Failed to parse agent output: %s. Raw: %s", exc, output_raw)
        raise 
