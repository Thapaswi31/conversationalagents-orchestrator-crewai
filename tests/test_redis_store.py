import json
import unittest
from unittest.mock import AsyncMock

from app.memory import redis_store


class RedisStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis = AsyncMock()
        self.original_client = redis_store.redis_client
        redis_store.redis_client = self.redis

    async def asyncTearDown(self):
        redis_store.redis_client = self.original_client

    async def test_get_history_returns_empty_list_when_key_missing(self):
        self.redis.get.return_value = None

        history = await redis_store.get_history("session-1")

        self.assertEqual(history, [])
        self.redis.get.assert_awaited_once_with("session:session-1:history")

    async def test_get_history_decodes_json_transcript(self):
        expected = [{"role": "user", "content": "hello"}]
        self.redis.get.return_value = json.dumps(expected)

        history = await redis_store.get_history("session-1")

        self.assertEqual(history, expected)

    async def test_save_history_serializes_with_one_hour_ttl(self):
        history = [{"role": "assistant", "content": "hi"}]

        await redis_store.save_history("session-1", history)

        self.redis.set.assert_awaited_once_with(
            "session:session-1:history",
            json.dumps(history),
            ex=3600,
        )

    async def test_delete_session_removes_history_key(self):
        await redis_store.delete_session("session-1")

        self.redis.delete.assert_awaited_once_with("session:session-1:history")


if __name__ == "__main__":
    unittest.main()
