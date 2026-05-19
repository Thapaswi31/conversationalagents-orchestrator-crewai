import asyncio
import unittest

from fastapi.testclient import TestClient

from app import main
from app.session import ConversationalSession


class InMemoryHistoryStore:
    def __init__(self):
        self.histories = {}

    async def get_history(self, session_id):
        return list(self.histories.get(session_id, []))

    async def save_history(self, session_id, history):
        self.histories[session_id] = list(history)


class ScriptedCrew:
    def __init__(self, calls, delay=0):
        self.calls = calls
        self.delay = delay

    async def kickoff_async(self, inputs=None):
        inputs = inputs or {}
        if self.delay:
            await asyncio.sleep(self.delay)

        message = inputs["user_message"].lower()
        call = {
            "message": inputs["user_message"],
            "conversation_context": inputs["conversation_context"],
            "tool_context": inputs["tool_context"],
            "tool": None,
        }

        if "research" in message:
            call["tool"] = "research_workflow"
            reply = "Research result: vector databases use embeddings for retrieval."
        elif "analyze" in message or "anomal" in message:
            call["tool"] = "data_analysis_workflow"
            reply = "Analysis result: Q3 sales show a South region churn anomaly."
        elif "what is my nickname" in message and "nickname is sky" in inputs["conversation_context"].lower():
            reply = "Your nickname is Sky."
        else:
            reply = "Chitchat reply."

        self.calls.append(call)
        return reply


class Phase8EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryHistoryStore()
        self.calls = []

        def session_factory(session_id):
            return ConversationalSession(
                session_id=session_id,
                store=self.store,
                crew_factory=lambda: ScriptedCrew(self.calls),
            )

        main.app.state.session_factory = session_factory

    def tearDown(self):
        if hasattr(main.app.state, "session_factory"):
            delattr(main.app.state, "session_factory")

    def test_multi_turn_chitchat_carries_history_without_tools(self):
        with TestClient(main.app) as client:
            first = client.post(
                "/chat",
                json={"session_id": "chatty", "message": "My nickname is Sky."},
            )
            second = client.post(
                "/chat",
                json={"session_id": "chatty", "message": "What is my nickname?"},
            )

        self.assertEqual(first.json()["status"], "ok")
        self.assertEqual(second.json()["reply"], "Your nickname is Sky.")
        self.assertIsNone(self.calls[0]["tool"])
        self.assertIsNone(self.calls[1]["tool"])
        self.assertIn("My nickname is Sky.", self.calls[1]["conversation_context"])

    def test_research_prompt_triggers_research_workflow_path(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/chat",
                json={"session_id": "research", "message": "research vector databases"},
            )

        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(self.calls[0]["tool"], "research_workflow")
        self.assertIn("vector databases", response.json()["reply"])

    def test_analysis_prompt_triggers_data_analysis_workflow_path(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/chat",
                json={
                    "session_id": "analysis",
                    "message": "analyze Q3 sales for anomalies",
                },
            )

        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(self.calls[0]["tool"], "data_analysis_workflow")
        self.assertIn("Q3 sales", response.json()["reply"])

    def test_context_carryover_passes_prior_research_to_analysis_turn(self):
        with TestClient(main.app) as client:
            client.post(
                "/chat",
                json={"session_id": "carryover", "message": "research topic X"},
            )
            client.post(
                "/chat",
                json={
                    "session_id": "carryover",
                    "message": "analyze what you just found",
                },
            )

        self.assertEqual(self.calls[0]["tool"], "research_workflow")
        self.assertEqual(self.calls[1]["tool"], "data_analysis_workflow")
        self.assertIn("research topic X", self.calls[1]["tool_context"])
        self.assertIn("Research result", self.calls[1]["tool_context"])

    def test_session_restore_loads_existing_history_from_store(self):
        with TestClient(main.app) as client:
            client.post(
                "/chat",
                json={"session_id": "restore", "message": "My nickname is Sky."},
            )

        with TestClient(main.app) as restarted_client:
            response = restarted_client.post(
                "/chat",
                json={"session_id": "restore", "message": "What is my nickname?"},
            )

        self.assertEqual(response.json()["reply"], "Your nickname is Sky.")
        self.assertIn("My nickname is Sky.", self.calls[-1]["conversation_context"])


class Phase8ConcurrentSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_sessions_do_not_bleed_history(self):
        store = InMemoryHistoryStore()
        calls = []

        def make_session(session_id):
            return ConversationalSession(
                session_id=session_id,
                store=store,
                crew_factory=lambda: ScriptedCrew(calls, delay=0.01),
            )

        first, second = await asyncio.gather(
            make_session("alpha").process_message("My nickname is Sky."),
            make_session("beta").process_message("hello from beta"),
        )

        self.assertEqual(first, "Chitchat reply.")
        self.assertEqual(second, "Chitchat reply.")
        self.assertIn("alpha", store.histories)
        self.assertIn("beta", store.histories)
        self.assertIn("My nickname is Sky.", store.histories["alpha"][0]["content"])
        self.assertIn("hello from beta", store.histories["beta"][0]["content"])
        contexts_by_message = {
            call["message"]: call["conversation_context"]
            for call in calls
        }
        self.assertNotIn("hello from beta", contexts_by_message["My nickname is Sky."])
        self.assertNotIn("My nickname is Sky.", contexts_by_message["hello from beta"])


if __name__ == "__main__":
    unittest.main()
