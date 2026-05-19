from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from redis import asyncio as redis


load_dotenv()

SESSION_TTL_SECONDS = 3600
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def _history_key(session_id: str) -> str:
    return f"session:{session_id}:history"


async def get_history(session_id: str) -> list[dict[str, str]]:
    stored_history = await redis_client.get(_history_key(session_id))
    if not stored_history:
        return []

    history: Any = json.loads(stored_history)
    if not isinstance(history, list):
        return []

    return [
        {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
        for item in history
        if isinstance(item, dict)
    ]


async def save_history(session_id: str, history: list[dict[str, str]]) -> None:
    await redis_client.set(
        _history_key(session_id),
        json.dumps(history),
        ex=SESSION_TTL_SECONDS,
    )


async def delete_session(session_id: str) -> None:
    await redis_client.delete(_history_key(session_id))
