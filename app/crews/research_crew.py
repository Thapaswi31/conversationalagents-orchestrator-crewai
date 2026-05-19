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
# Redis-backed session memory is a later app concern; crew construction should
# remain testable even when Redis is not running.
_redis_url = os.environ.pop("REDIS_URL", None)
from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool

if _redis_url is not None:
    os.environ["REDIS_URL"] = _redis_url


def _default_context(inputs: dict) -> dict:
    return {**inputs, "context": inputs.get("context", "")}

def create_research_crew() -> Crew:
    """Create the research crew with a researcher and writer."""
    search_tool = SerperDevTool()

    researcher = Agent(
        role="Senior Research Analyst",
        goal=(
            "Find accurate, current information for the given query, verify it "
            "across multiple sources, and synthesize the most important facts."
        ),
        backstory=(
            "You are a meticulous research analyst who checks source quality, "
            "compares claims, and separates confirmed facts from speculation."
        ),
        tools=[search_tool],
        verbose=True, # enable detailed logging for better traceability
        allow_delegation=False, # stop allowing tasks to delegate to other agents after 3 iterations to prevent infinite loops
        max_iter=3,        # stop looping after 3 searches
        #max_tokens=1024,   # prevent overly long outputs
        temperature=0.3,   # more focused, less creative
        cache=True,        # don't repeat identical searches
        llm=os.getenv("OLLAMA_MODEL"),

    )

    writer = Agent(
        role="Technical Content Writer",
        goal=(
            "Transform raw research notes into clean, structured markdown "
            "summaries that are concise, readable, and technically precise."
        ),
        backstory=(
            "You are a technical writer who turns messy research into crisp "
            "executive-ready summaries without adding unsupported claims."
        ),
        tools=[],
        verbose=True,
        allow_delegation=False,
        max_iter=1,        # no tools, no looping needed
        temperature=0.5,   # balance between precise and readable
        llm=os.getenv("OLLAMA_MODEL"),
    )

    research_task = Task(
        description=(
            "Research the query: {query}\n\n"
            "Recent conversation context, if any:\n{context}\n\n"
            "Use web search to find accurate and current information. Verify "
            "important claims across multiple sources and capture source names "
            "or URLs where available."
        ),
        expected_output=(
            "Raw research notes and facts, including verified claims, useful "
            "source references, and any caveats or disagreements between sources."
        ),
        agent=researcher,
    )

    writing_task = Task(
        description=(
            "Use the research notes to write a clear markdown summary for the "
            "query. Preserve source-grounded nuance and avoid unsupported claims."
        ),
        expected_output=(
            "A 2-3 paragraph markdown summary with the key findings, current "
            "context, and relevant caveats."
        ),
        agent=writer,
        context=[research_task],
    )

    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        process=Process.sequential,
        verbose=True,
        tracing=True,
        before_kickoff_callbacks=[_default_context],
    )


if __name__ == "__main__":
    crew = create_research_crew()
    result = crew.kickoff(inputs={"query": "latest trends in vector databases"})
    print(result)
