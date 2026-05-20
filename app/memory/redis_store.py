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


def _agent_key(agent_id: str) -> str:
    return f"agent:{agent_id}:data"


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


async def save_agent(agent_id: str, data: dict[str, any]) -> None:
    await redis_client.set(_agent_key(agent_id), json.dumps(data))


async def get_agent(agent_id: str) -> dict | None:
    raw = await redis_client.get(_agent_key(agent_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def list_agents() -> list[str]:
    # keys pattern -- may be inefficient for large datasets but fine for demo
    keys = await redis_client.keys("agent:*:data")
    ids = []
    for k in keys:
        # extract between 'agent:' and ':data'
        if k.startswith("agent:") and k.endswith(":data"):
            ids.append(k.split(":")[1])
    return ids


async def delete_agent(agent_id: str) -> None:
    await redis_client.delete(_agent_key(agent_id))
