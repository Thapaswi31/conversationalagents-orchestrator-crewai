from __future__ import annotations

import json
import os
import uuid
from typing import Optional

from dotenv import load_dotenv

from crewai import Agent

from app.memory import redis_store
from app.tools import research_tool, analysis_tool

load_dotenv()


async def create_agent(definition: dict) -> str:
    """Persist an agent definition and return its id."""
    agent_id = str(uuid.uuid4())
    await redis_store.save_agent(agent_id, definition)
    return agent_id


async def get_agent_definition(agent_id: str) -> Optional[dict]:
    return await redis_store.get_agent(agent_id)


async def list_agent_ids() -> list[str]:
    return await redis_store.list_agents()


def _resolve_tools(tool_names: list[str] | None) -> list:
    if not tool_names:
        return []
    resolved = []
    for name in tool_names:
        if name == "research_workflow":
            resolved.append(research_tool.research_workflow)
        elif name == "data_analysis_workflow":
            resolved.append(analysis_tool.data_analysis_workflow)
        else:
            # unknown tool; skip for now
            continue
    return resolved


def instantiate_agent_from_definition(definition: dict) -> Agent:
    """Create a CrewAI Agent from a saved definition.

    Expected fields: role, goal, backstory (optional), tools (optional list of names),
    temperature, allow_delegation, max_iter, memory, llm
    """
    tools = _resolve_tools(definition.get("tools"))
    agent = Agent(
        role=definition.get("role", "Custom Agent"),
        goal=definition.get("goal", "Assist the user."),
        backstory=definition.get("backstory", ""),
        tools=tools,
        memory=definition.get("memory", False),
        verbose=definition.get("verbose", True),
        allow_delegation=definition.get("allow_delegation", False),
        max_iter=definition.get("max_iter", 3),
        temperature=definition.get("temperature", 0.5),
        llm=os.getenv("OLLAMA_MODEL"),
    )
    return agent


async def instantiate_agent_agentid(agent_id: str) -> Optional[Agent]:
    definition = await get_agent_definition(agent_id)
    if not definition:
        return None
    return instantiate_agent_from_definition(definition)
