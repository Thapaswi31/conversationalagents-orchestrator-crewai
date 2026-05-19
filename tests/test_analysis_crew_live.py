import os
import time
import unittest
from pathlib import Path


os.environ.setdefault(
    "CREWAI_STORAGE_DIR",
    str(Path(__file__).resolve().parents[1] / ".crewai-storage"),
)

from app.crews.analysis_crew import create_analysis_crew


def _has_llm_config() -> bool:
    openai_key = os.getenv("OPENAI_API_KEY", "")
    has_openai_key = openai_key.startswith("sk-") and openai_key != "sk-..."
    return bool(os.getenv("OLLAMA_MODEL") or has_openai_key)


@unittest.skipUnless(
    os.getenv("RUN_LIVE_ANALYSIS_CREW") == "1" and _has_llm_config(),
    "Set RUN_LIVE_ANALYSIS_CREW=1 with OLLAMA_MODEL or a real OPENAI_API_KEY.",
)
class LiveAnalysisCrewTests(unittest.TestCase):
    def test_analysis_crew_returns_data_specific_reports_for_two_inputs(self):
        examples = [
            {
                "dataset": (
                    "Region,Revenue,Churn\n"
                    "North,125000,3.1%\n"
                    "South,98000,7.8%\n"
                    "West,143000,2.9%"
                ),
                "question": "Which region needs retention attention and why?",
                "expected_terms": ["South", "7.8"],
            },
            {
                "dataset": (
                    "Channel,Leads,ConversionRate\n"
                    "Organic,480,12.5%\n"
                    "Paid Search,320,8.2%\n"
                    "Partner,140,18.6%"
                ),
                "question": "Which channel is most efficient for conversion?",
                "expected_terms": ["Partner", "18.6"],
            },
        ]

        for example in examples:
            with self.subTest(question=example["question"]):
                crew = create_analysis_crew()

                started_at = time.monotonic()
                result = crew.kickoff(
                    inputs={
                        "dataset": example["dataset"],
                        "question": example["question"],
                    }
                )
                elapsed = time.monotonic() - started_at

                report = str(result)
                self.assertLess(elapsed, 60)
                self.assertGreater(len(report), 200)
                for term in example["expected_terms"]:
                    self.assertIn(term, report)


if __name__ == "__main__":
    unittest.main()
