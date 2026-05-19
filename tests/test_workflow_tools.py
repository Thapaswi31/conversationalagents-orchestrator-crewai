import unittest
from unittest.mock import patch

from app.tools.analysis_tool import data_analysis_workflow
from app.tools.research_tool import research_workflow


class FakeCrew:
    def __init__(self, result: str = "workflow result", error: Exception | None = None):
        self.inputs = None
        self.result = result
        self.error = error

    def kickoff(self, inputs):
        self.inputs = inputs
        if self.error:
            raise self.error
        return self.result


class WorkflowToolTests(unittest.TestCase):
    def test_research_tool_docstring_and_context_injection(self):
        fake_crew = FakeCrew("research summary")

        with patch(
            "app.tools.research_tool.create_research_crew",
            return_value=fake_crew,
        ):
            result = research_workflow.run(
                query="vector database trends",
                context="Recent chat: user prefers concise summaries.",
            )

        self.assertEqual(result, "research summary")
        self.assertEqual(
            fake_crew.inputs,
            {
                "query": "vector database trends",
                "context": "Recent chat: user prefers concise summaries.",
            },
        )
        self.assertEqual(research_workflow.name, "research_workflow")
        self.assertIn("Use ONLY when", research_workflow.description)
        self.assertIn("Do NOT use for data or metrics questions", research_workflow.description)

    def test_research_tool_returns_graceful_error(self):
        with patch(
            "app.tools.research_tool.create_research_crew",
            return_value=FakeCrew(error=RuntimeError("Serper failed")),
        ):
            result = research_workflow.run(query="market news")

        self.assertIn("Research workflow failed", result)
        self.assertIn("Serper failed", result)

    def test_analysis_tool_docstring_and_context_injection(self):
        fake_crew = FakeCrew("analysis report")

        with patch(
            "app.tools.analysis_tool.create_analysis_crew",
            return_value=fake_crew,
        ):
            result = data_analysis_workflow.run(
                dataset="Region,Revenue\nNorth,100",
                question="Which region leads?",
                context="Recent chat: user cares about revenue.",
            )

        self.assertEqual(result, "analysis report")
        self.assertEqual(
            fake_crew.inputs,
            {
                "dataset": "Region,Revenue\nNorth,100",
                "question": "Which region leads?",
                "context": "Recent chat: user cares about revenue.",
            },
        )
        self.assertEqual(data_analysis_workflow.name, "data_analysis_workflow")
        self.assertIn("Use ONLY when", data_analysis_workflow.description)
        self.assertIn("Do NOT use for general research", data_analysis_workflow.description)

    def test_analysis_tool_returns_graceful_error(self):
        with patch(
            "app.tools.analysis_tool.create_analysis_crew",
            return_value=FakeCrew(error=RuntimeError("analysis failed")),
        ):
            result = data_analysis_workflow.run(
                dataset="Region,Revenue\nNorth,100",
                question="Which region leads?",
            )

        self.assertIn("Data analysis workflow failed", result)
        self.assertIn("analysis failed", result)


if __name__ == "__main__":
    unittest.main()
