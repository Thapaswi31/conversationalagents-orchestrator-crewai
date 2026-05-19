from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


_APP_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(_APP_ROOT / ".env")
os.environ.setdefault("CREWAI_STORAGE_DIR", str(_APP_ROOT / ".crewai-storage"))

_redis_url = os.environ.pop("REDIS_URL", None)
from crewai import Agent

from app.tools.analysis_tool import data_analysis_workflow
from app.tools.research_tool import research_workflow

if _redis_url is not None:
    os.environ["REDIS_URL"] = _redis_url


conversational_agent = Agent(
    role="Conversational Assistant",
    goal=(
        "Help users by chatting naturally and invoking specialized workflows "
        "only when explicitly needed."
    ),
    backstory=(
        "You are a helpful conversational assistant. Answer directly when the "
        "request can be handled in normal conversation. Use the research "
        "workflow only for explicit research, fact-finding, or summary requests. "
        "Use the data analysis workflow only when the user provides data, "
        "numbers, or metrics and asks for analysis."
    ),
    tools=[research_workflow, data_analysis_workflow],
    memory=False,
    verbose=True,
    tracing=True,
    max_iter=3,        # max 3 tool calls per turn
    temperature=0.5, # balance between precise and readable
    allow_delegation=False,
    llm=os.getenv("OLLAMA_MODEL"),
)


def get_conversational_agent() -> Agent:
    """Return the shared module-level conversational agent singleton."""
    return conversational_agent
