from __future__ import annotations

import os
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("CREWAI_STORAGE_DIR", str(_APP_ROOT / ".crewai-storage"))

_redis_url = os.environ.pop("REDIS_URL", None)
from crewai.tools import tool
from app.crews.analysis_crew import create_analysis_crew

if _redis_url is not None:
    os.environ["REDIS_URL"] = _redis_url


@tool("data_analysis_workflow")
def data_analysis_workflow(dataset: str, question: str, context: str = "") -> str:
    """Use ONLY when the user provides data/numbers/metrics and asks for analysis, anomaly detection, or trend identification. Do NOT use for general research."""
    try:
        crew = create_analysis_crew()
        result = crew.kickoff(
            inputs={
                "dataset": dataset,
                "question": question,
                "context": context,
            }
        )
        return str(result)
    except Exception as exc:
        return f"Data analysis workflow failed: {exc}"
