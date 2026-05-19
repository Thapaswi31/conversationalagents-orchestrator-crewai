import io
import json
import sys
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.RequestException = Exception
    sys.modules["requests"] = requests_stub

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:
        pass

    def Field(default, description=None):
        return default

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    sys.modules["pydantic"] = pydantic_stub

if "crewai" not in sys.modules:
    crewai_stub = types.ModuleType("crewai")
    crewai_tools_stub = types.ModuleType("crewai.tools")

    class BaseTool:
        pass

    crewai_tools_stub.BaseTool = BaseTool
    sys.modules["crewai"] = crewai_stub
    sys.modules["crewai.tools"] = crewai_tools_stub

import workflowcallertool


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.text = str(payload)

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeRequests:
    RequestException = Exception

    def __init__(self):
        self.post_calls = []
        self.get_calls = []

    def post(self, url, files, headers, verify=True):
        self.post_calls.append({"url": url, "files": files, "headers": headers, "verify": verify})
        return FakeResponse(
            {
                "data": {
                    "message": "Job submitted successfully",
                    "workflowExecutionId": "234408e6-5aed-463e-81ee-3b5c35e50dab",
                    "jobId": 3062,
                },
                "status": "SUCCESS",
            }
        )

    def get(self, url, headers, params=None, verify=True):
        self.get_calls.append({"url": url, "headers": headers, "params": params, "verify": verify})

        if url.endswith("/logs"):
            return FakeResponse({"data": [{"message": "Generated UX design"}], "status": "SUCCESS"})

        return FakeResponse(
            {
                "data": {
                    "workflowExecutionResponseList": [
                        {
                            "id": 3062,
                            "pipelineId": 1453,
                            "executionId": "234408e6-5aed-463e-81ee-3b5c35e50dab",
                            "workflowName": "UX Design Pipeline SCIB",
                            "userSignature": "madishetti.thapaswi@ascendion.com",
                            "status": "COMPLETED",
                        }
                    ]
                },
                "status": "SUCCESS",
            }
        )


class WorkflowCallerToolMainTests(unittest.TestCase):
    def test_main_runs_workflow_with_requested_jira_and_pipeline(self):
        calls = []

        class FakeRestApiCaller:
            def _run(self, pipelineId, jiraInput):
                calls.append((pipelineId, jiraInput))
                return "workflow response"

        output = io.StringIO()

        with patch.object(workflowcallertool, "RestApiCaller", FakeRestApiCaller):
            with redirect_stdout(output):
                workflowcallertool.main([])

        self.assertEqual(calls, [(1918, "SCIB-1071")])
        self.assertEqual(output.getvalue(), "workflow response\n")

    def test_main_can_poll_existing_execution_without_triggering_workflow(self):
        calls = []

        class FakeRestApiCaller:
            def _run(self, pipelineId, jiraInput):
                raise AssertionError("_run should not trigger a new workflow")

            def get_existing_execution_result(self, execution_id):
                calls.append(execution_id)
                return "existing workflow response"

        output = io.StringIO()

        with patch.object(workflowcallertool, "RestApiCaller", FakeRestApiCaller):
            with redirect_stdout(output):
                workflowcallertool.main(
                    ["--execution-id", "af431d2b-09ea-4f30-ad6c-3fb83bddf3cf"]
                )

        self.assertEqual(calls, ["af431d2b-09ea-4f30-ad6c-3fb83bddf3cf"])
        self.assertEqual(output.getvalue(), "existing workflow response\n")

    def test_run_triggers_workflow_fetches_status_and_logs(self):
        fake_requests = FakeRequests()

        with patch.object(workflowcallertool, "requests", fake_requests):
            result = workflowcallertool.RestApiCaller()._run(
                pipelineId=1918,
                jiraInput="SCIB-1071",
            )

        self.assertIn("workflowExecutionId: 234408e6-5aed-463e-81ee-3b5c35e50dab", result)
        self.assertIn("jobId: 3062", result)
        self.assertIn("status: COMPLETED", result)
        self.assertIn("Generated UX design", result)
        self.assertEqual(
            fake_requests.get_calls[0]["url"],
            "https://ext.avateam.io/workflows/workflow-executions",
        )
        self.assertEqual(
            fake_requests.get_calls[0]["params"],
            {"execution-id": "234408e6-5aed-463e-81ee-3b5c35e50dab"},
        )
        self.assertFalse(fake_requests.post_calls[0]["verify"])
        self.assertFalse(fake_requests.get_calls[0]["verify"])
        self.assertEqual(
            fake_requests.get_calls[1]["url"],
            "https://ext.avateam.io/workflows/workflow-executions/234408e6-5aed-463e-81ee-3b5c35e50dab/logs",
        )
        self.assertFalse(fake_requests.get_calls[1]["verify"])

    def test_poll_execution_logs_waits_until_logs_report_terminal_status(self):
        payloads = [
            {"data": [{"message": "Agent 1 finished"}], "status": "IN_PROGRESS"},
            {"data": [{"message": "Agent 2 finished"}], "status": "IN_PROGRESS"},
            {"data": [{"message": "All agents finished"}], "status": "COMPLETED"},
        ]

        class FakeLogRequests:
            RequestException = Exception

            def __init__(self):
                self.get_calls = []

            def get(self, url, headers, params=None, verify=True):
                self.get_calls.append({"url": url, "headers": headers, "params": params})
                return FakeResponse(payloads.pop(0))

        fake_requests = FakeLogRequests()

        with patch.object(workflowcallertool, "requests", fake_requests):
            logs_payload = workflowcallertool.RestApiCaller()._poll_execution_logs(
                headers={"Authorization": "Bearer token"},
                execution_id="65ea6b73-8a7d-4f06-b4b2-56370966ec90",
                max_attempts=3,
                poll_interval_seconds=0,
            )

        self.assertEqual(logs_payload["status"], "COMPLETED")
        self.assertEqual(logs_payload["data"][0]["message"], "All agents finished")
        self.assertEqual(len(fake_requests.get_calls), 3)

    def test_format_result_returns_only_final_answer_when_available(self):
        trigger_payload = {
            "data": {
                "workflowExecutionId": "65ea6b73-8a7d-4f06-b4b2-56370966ec90",
                "jobId": 3062,
            }
        }
        status_payload = {
            "data": {
                "workflowExecutionResponseList": [
                    {"status": "SUCCESS"},
                ]
            }
        }
        logs_payload = {
            "data": [
                {
                    "logs": json.dumps(
                        {
                            "content": "\n\n\u001b[1m\u001b[95m# Agent:\u001b[00m Senior UI Design System Integration Engineer",
                        }
                    )
                },
                {
                    "logs": json.dumps(
                        {
                            "content": "\u001b[95m## Final Answer:\u001b[00m \u001b[92m\nCreated the high-fidelity UI.\u001b[00m\n\n",
                        }
                    )
                },
                {
                    "logs": json.dumps(
                        {
                            "progress": "FINISHED",
                            "content": "Pipeline Execution Completed",
                        }
                    )
                },
            ],
            "status": "SUCCESS",
        }

        result = workflowcallertool.RestApiCaller()._format_result(
            trigger_payload,
            status_payload,
            logs_payload,
        )

        self.assertEqual(result, "Created the high-fidelity UI.")
        self.assertNotIn("Workflow submitted successfully", result)
        self.assertNotIn("# Agent", result)
        self.assertNotIn("Pipeline Execution Completed", result)

    def test_format_result_handles_raw_string_log_entries(self):
        result = workflowcallertool.RestApiCaller()._format_result(
            {"data": {"workflowExecutionId": "execution-1"}},
            {"data": {"workflowExecutionResponseList": [{"status": "SUCCESS"}]}},
            {
                "data": [
                    "intermediate log line",
                    "\u001b[95m## Final Answer:\u001b[00m \u001b[92m\nFinal text from raw string.\u001b[00m",
                ],
                "status": "SUCCESS",
            },
        )

        self.assertEqual(result, "Final text from raw string.")


if __name__ == "__main__":
    unittest.main()
