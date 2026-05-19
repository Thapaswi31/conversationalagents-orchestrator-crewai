import os
import time
import unittest
from pathlib import Path


os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(__file__).resolve().parents[1] / ".crewai-storage"),
)

from app.crews.research_crew import create_research_crew


def _has_real_api_keys() -> bool:
    openai_key = os.getenv("OPENAI_API_KEY", "")
    serper_key = os.getenv("SERPER_API_KEY", "")
    return openai_key.startswith("sk-") and openai_key != "sk-..." and serper_key != "..."


@unittest.skipUnless(
    os.getenv("RUN_LIVE_RESEARCH_CREW") == "1" and _has_real_api_keys(),
    "Set RUN_LIVE_RESEARCH_CREW=1 with real OPENAI_API_KEY and SERPER_API_KEY.",
)
class LiveResearchCrewTests(unittest.TestCase):
    def test_research_crew_returns_summaries_for_two_queries_under_sixty_seconds(self):
        queries = [
            "latest trends in vector databases",
            "current best practices for evaluating RAG systems",
        ]

        for query in queries:
            with self.subTest(query=query):
                crew = create_research_crew()

                started_at = time.monotonic()
                result = crew.kickoff(inputs={"query": query})
                elapsed = time.monotonic() - started_at

                summary = str(result)
                self.assertLess(elapsed, 60)
                self.assertGreater(len(summary), 300)
                self.assertIn("\n", summary)


if __name__ == "__main__":
    unittest.main()
