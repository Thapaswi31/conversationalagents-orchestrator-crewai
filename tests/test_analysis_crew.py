import os
import unittest
from pathlib import Path


os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(__file__).resolve().parents[1] / ".crewai-storage"),
)

from app.crews.analysis_crew import create_analysis_crew


class AnalysisCrewTests(unittest.TestCase):
    def test_analysis_crew_has_analyst_reporter_and_task_context(self):
        crew = create_analysis_crew()

        self.assertEqual(len(crew.agents), 2)
        self.assertEqual(crew.agents[0].role, "Data Analyst")
        self.assertEqual(crew.agents[1].role, "Business Reporter")
        self.assertEqual(crew.agents[0].tools, [])
        self.assertEqual(crew.agents[1].tools, [])

        self.assertEqual(len(crew.tasks), 2)
        analysis_task, reporting_task = crew.tasks
        self.assertIs(reporting_task.context[0], analysis_task)
        self.assertIn("{dataset}", analysis_task.description)
        self.assertIn("{question}", analysis_task.description)
        self.assertIn("bullet-point findings", analysis_task.expected_output)
        self.assertIn("2-3 paragraph plain-English report", reporting_task.expected_output)

    def test_analysis_crew_supports_sync_and_async_kickoff(self):
        crew = create_analysis_crew()

        self.assertTrue(callable(crew.kickoff))
        self.assertTrue(callable(crew.kickoff_async))

    def test_analysis_crew_defaults_context_for_standalone_kickoff_inputs(self):
        crew = create_analysis_crew()

        normalized = crew.before_kickoff_callbacks[0](
            {
                "dataset": "Region,Revenue\nNorth,100",
                "question": "Which region leads?",
            }
        )

        self.assertEqual(normalized["context"], "")

    def test_analysis_crew_preserves_explicit_context(self):
        crew = create_analysis_crew()

        normalized = crew.before_kickoff_callbacks[0](
            {
                "dataset": "Region,Revenue\nNorth,100",
                "question": "Which region leads?",
                "context": "Previous chat context.",
            }
        )

        self.assertEqual(normalized["context"], "Previous chat context.")


if __name__ == "__main__":
    unittest.main()
