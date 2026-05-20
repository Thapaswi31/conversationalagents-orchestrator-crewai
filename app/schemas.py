from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    agent_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    status: Literal["ok", "error"]


class AgentCreateRequest(BaseModel):
    role: str
    goal: str
    backstory: str | None = None
    tools: list[str] | None = None


class AgentCreateResponse(BaseModel):
    agent_id: str
    status: Literal["ok", "error"]
