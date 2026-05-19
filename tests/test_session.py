import unittest
from unittest.mock import AsyncMock

from app.session import ConversationalSession


class FakeCrew:
    def __init__(self, reply="assistant reply"):
        self.reply = reply
        self.inputs = None

    async def kickoff_async(self, inputs=None):
        self.inputs = inputs or {}
        return self.reply


class FakeStore:
    def __init__(self, history=None):
        self.history = history or []
        self.saved = None

    async def get_history(self, session_id):
        return list(self.history)

    async def save_history(self, session_id, history):
        self.saved = (session_id, history)


class ConversationalSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_message_loads_history_runs_crew_and_saves_reply(self):
        store = FakeStore(
            [
                {"role": "user", "content": "My project is Aurora."},
                {"role": "assistant", "content": "Got it."},
            ]
        )
        crew = FakeCrew("Sure, Aurora is the project.")
        session = ConversationalSession(
            session_id="abc123",
            store=store,
            crew_factory=lambda: crew,
        )

        reply = await session.process_message("What is my project?")

        self.assertEqual(reply, "Sure, Aurora is the project.")
        self.assertEqual(store.saved[0], "abc123")
        self.assertEqual(
            store.saved[1],
            [
                {"role": "user", "content": "My project is Aurora."},
                {"role": "assistant", "content": "Got it."},
                {"role": "user", "content": "What is my project?"},
                {"role": "assistant", "content": "Sure, Aurora is the project."},
            ],
        )
        self.assertIn("My project is Aurora.", crew.inputs["conversation_context"])
        self.assertIn("last 2 turns", crew.inputs["tool_context_instruction"])

    async def test_process_message_summarizes_older_history_when_over_twenty_turns(self):
        history = []
        for index in range(21):
            history.append({"role": "user", "content": f"user {index}"})
            history.append({"role": "assistant", "content": f"assistant {index}"})

        store = FakeStore(history)
        crew = FakeCrew("summarized reply")
        summarizer = AsyncMock(return_value="Summary of older turns.")
        session = ConversationalSession(
            session_id="long-session",
            store=store,
            crew_factory=lambda: crew,
            summarizer=summarizer,
        )

        await session.process_message("new question")

        summarizer.assert_awaited_once()
        saved_history = store.saved[1]
        self.assertEqual(saved_history[0]["role"], "system")
        self.assertIn("Summary of older turns.", saved_history[0]["content"])
        self.assertLessEqual(len(saved_history), 22)
        self.assertIn("Summary of older turns.", crew.inputs["conversation_context"])
        self.assertIn("user 20", crew.inputs["conversation_context"])
        self.assertNotIn("user 0", crew.inputs["conversation_context"])


if __name__ == "__main__":
    unittest.main()
