from __future__ import annotations

import os
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("CREWAI_STORAGE_DIR", str(_APP_ROOT / ".crewai-storage"))

_redis_url = os.environ.pop("REDIS_URL", None)
from crewai.tools import tool
from app.crews.research_crew import create_research_crew

if _redis_url is not None:
    os.environ["REDIS_URL"] = _redis_url


@tool("research_workflow")
def research_workflow(query: str, context: str = "") -> str:
    """Use ONLY when the user asks to research a topic, find facts, get a summary. Do NOT use for data or metrics questions."""
    try:
        crew = create_research_crew()
        result = crew.kickoff(inputs={"query": query, "context": context})
        return str(result)
    except Exception as exc:
        return f"Research workflow failed: {exc}"
