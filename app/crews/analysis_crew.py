from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


_APP_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(_APP_ROOT / ".env")
os.environ["OPENAI_API_BASE"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ["OPENAI_API_KEY"] = "ollama"  # dummy key (required but not used)
os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(_APP_ROOT / ".crewai-storage"),
)

# CrewAI's lock module chooses Redis during import if REDIS_URL is present.
# Redis-backed session memory belongs to the API/session layer, while this
# crew should be constructible and testable on its own.
_redis_url = os.environ.pop("REDIS_URL", None)
from crewai import Agent, Crew, Process, Task

if _redis_url is not None:
    os.environ["REDIS_URL"] = _redis_url


def _default_context(inputs: dict) -> dict:
    return {**inputs, "context": inputs.get("context", "")}


def create_analysis_crew() -> Crew:
    """Create the data analysis crew with an analyst and reporter."""

    analyst = Agent(
        role="Data Analyst",
        goal=(
            "Interpret structured data or textual descriptions, identify "
            "patterns and anomalies, and answer the user's specific question."
        ),
        backstory=(
            "You are a careful analyst who grounds every finding in the data "
            "provided and avoids generic filler or unsupported assumptions."
        ),
        tools=[],
        verbose=True,
        allow_delegation=False,
        max_iter=1, # no tools, no looping
        temperature=0.3,   # precise with numbers
        llm=os.getenv("OLLAMA_MODEL"),
    )

    reporter = Agent(
        role="Business Reporter",
        goal=(
            "Translate analyst findings into actionable business insights in "
            "plain language for decision-makers."
        ),
        backstory=(
            "You are a business reporter who turns analytical findings into "
            "clear recommendations, risks, and next steps without jargon."
        ),
        tools=[],
        verbose=True,
        allow_delegation=False,
        max_iter=1, # no tools, no looping
        temperature=0.5,   # readable prose
        llm=os.getenv("OLLAMA_MODEL"),
    )

    analysis_task = Task(
        description=(
            "Analyze this dataset or data description:\n\n{dataset}\n\n"
            "Answer this question: {question}\n\n"
            "Recent conversation context, if any:\n{context}\n\n"
            "Identify patterns, anomalies, and specific data-backed answers. "
            "Use only the data provided."
        ),
        expected_output=(
            "Specific bullet-point findings grounded in the provided data, "
            "including patterns, anomalies, and a direct answer to the question."
        ),
        agent=analyst,
    )

    reporting_task = Task(
        description=(
            "Turn the analyst findings into a concise plain-English business "
            "report. Make the insights actionable and specific to the supplied "
            "data."
        ),
        expected_output=(
            "A 2-3 paragraph plain-English report with actionable business "
            "insights, key risks or anomalies, and recommended next steps."
        ),
        agent=reporter,
        context=[analysis_task],
    )

    return Crew(
        agents=[analyst, reporter],
        tasks=[analysis_task, reporting_task],
        process=Process.sequential,
        verbose=True,
        tracing=True,
        before_kickoff_callbacks=[_default_context],
    )


if __name__ == "__main__":
    crew = create_analysis_crew()
    result = crew.kickoff(
        inputs={
            "dataset": (
                "Region,Revenue,Churn\n"
                "North,125000,3.1%\n"
                "South,98000,7.8%\n"
                "West,143000,2.9%"
            ),
            "question": "Which region needs retention attention and why?",
        }
    )
    print(result)
