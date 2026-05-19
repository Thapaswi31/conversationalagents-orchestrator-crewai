import os
import unittest
from pathlib import Path


os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(__file__).resolve().parents[1] / ".crewai-storage"),
)

from app.crews.research_crew import create_research_crew


class ResearchCrewTests(unittest.TestCase):
    def test_research_crew_has_researcher_writer_and_task_context(self):
        crew = create_research_crew()

        self.assertEqual(len(crew.agents), 2)
        self.assertEqual(crew.agents[0].role, "Senior Research Analyst")
        self.assertEqual(crew.agents[1].role, "Technical Content Writer")
        self.assertTrue(crew.agents[0].tools)
        self.assertEqual(crew.agents[1].tools, [])

        self.assertEqual(len(crew.tasks), 2)
        research_task, writing_task = crew.tasks
        self.assertIs(writing_task.context[0], research_task)
        self.assertIn("{query}", research_task.description)
        self.assertIn("2-3 paragraph markdown summary", writing_task.expected_output)

    def test_research_crew_supports_sync_and_async_kickoff(self):
        crew = create_research_crew()

        self.assertTrue(callable(crew.kickoff))
        self.assertTrue(callable(crew.kickoff_async))

    def test_research_crew_defaults_context_for_standalone_kickoff_inputs(self):
        crew = create_research_crew()

        normalized = crew.before_kickoff_callbacks[0](
            {"query": "latest trends in vector databases"}
        )

        self.assertEqual(normalized["context"], "")

    def test_research_crew_preserves_explicit_context(self):
        crew = create_research_crew()

        normalized = crew.before_kickoff_callbacks[0](
            {
                "query": "latest trends in vector databases",
                "context": "Previous chat context.",
            }
        )

        self.assertEqual(normalized["context"], "Previous chat context.")


if __name__ == "__main__":
    unittest.main()
