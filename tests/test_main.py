import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import main


class FakeSession:
    instances = []

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages = []
        FakeSession.instances.append(self)

    async def process_message(self, message: str) -> str:
        self.messages.append(message)
        return f"reply to {message}"


class FastAPITests(unittest.TestCase):
    def setUp(self):
        FakeSession.instances = []
        main.app.state.session_factory = FakeSession

    def tearDown(self):
        if hasattr(main.app.state, "session_factory"):
            delattr(main.app.state, "session_factory")

    def test_chat_generates_session_id_when_absent_and_returns_reply(self):
        with TestClient(main.app) as client:
            response = client.post("/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["reply"], "reply to hello")
        self.assertTrue(body["session_id"])
        self.assertEqual(FakeSession.instances[0].session_id, body["session_id"])
        self.assertEqual(FakeSession.instances[0].messages, ["hello"])

    def test_chat_preserves_provided_session_id(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/chat",
                json={"session_id": "session-123", "message": "continue"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "session_id": "session-123",
                "reply": "reply to continue",
                "status": "ok",
            },
        )

    def test_chat_returns_error_response_when_session_processing_fails(self):
        class FailingSession:
            def __init__(self, session_id: str):
                self.session_id = session_id

            async def process_message(self, message: str) -> str:
                raise RuntimeError("crew failed")

        main.app.state.session_factory = FailingSession

        with TestClient(main.app) as client:
            response = client.post("/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertIn("crew failed", body["reply"])

    def test_delete_chat_clears_redis_history(self):
        with patch.object(main.redis_store, "delete_session", new=AsyncMock()) as delete:
            with TestClient(main.app) as client:
                response = client.delete("/chat/session-123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        delete.assert_awaited_once_with("session-123")

    def test_health_reports_redis_connected(self):
        with patch.object(main.redis_store.redis_client, "ping", new=AsyncMock(return_value=True)):
            with TestClient(main.app) as client:
                response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "redis": "connected"})

    def test_stream_endpoint_emits_server_sent_events(self):
        with TestClient(main.app) as client:
            with client.stream("GET", "/chat/session-123/stream") as response:
                body = response.read().decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertIn("event: progress", body)
        self.assertIn("event: complete", body)

    def test_stream_endpoint_processes_message_when_query_is_provided(self):
        with TestClient(main.app) as client:
            with client.stream(
                "GET",
                "/chat/session-123/stream",
                params={"message": "slow question"},
            ) as response:
                body = response.read().decode()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FakeSession.instances[0].session_id, "session-123")
        self.assertEqual(FakeSession.instances[0].messages, ["slow question"])
        self.assertIn("event: progress", body)
        self.assertIn("reply to slow question", body)
        self.assertIn("event: complete", body)


if __name__ == "__main__":
    unittest.main()
