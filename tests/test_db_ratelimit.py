import tempfile
import time
import unittest
from pathlib import Path

from cskh.db import Database
from cskh.ratelimit import RateLimiter


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.sqlite3")
        await self.db.open()
        await self.db.upsert_user(1, "A", "a")
        await self.db.upsert_user(2, "B", None)

    async def asyncTearDown(self):
        await self.db.close()
        self.tmp.cleanup()

    async def test_recent_messages_returns_newest_window_oldest_first(self):
        for i in range(15):
            await self.db.add_message(1, "user", f"m{i}")
        history = await self.db.recent_messages(1, 10)
        self.assertEqual([m["content"] for m in history], [f"m{i}" for i in range(5, 15)])

    async def test_history_is_per_user(self):
        await self.db.add_message(1, "user", "for-1")
        await self.db.add_message(2, "user", "for-2")
        self.assertEqual(await self.db.recent_messages(2, 10), [{"role": "user", "content": "for-2"}])

    async def test_purge_removes_only_old_messages(self):
        await self.db.add_message(1, "user", "old")
        await self.db.add_message(1, "user", "new")
        old = time.time() - 31 * 86400
        await self.db.conn.execute("UPDATE messages SET created_at = ? WHERE content = 'old'", (old,))
        await self.db.conn.commit()
        self.assertEqual(await self.db.purge_messages_older_than(30), 1)
        self.assertEqual([m["content"] for m in await self.db.recent_messages(1, 10)], ["new"])


class RateLimiterTests(unittest.TestCase):
    def test_blocks_over_limit_then_recovers_after_window(self):
        now = [0.0]
        limiter = RateLimiter(3, 60, clock=lambda: now[0])
        self.assertEqual([limiter.allow(1) for _ in range(4)], [True, True, True, False])
        self.assertTrue(limiter.allow(2))  # other user unaffected
        now[0] = 60.0
        self.assertTrue(limiter.allow(1))


if __name__ == "__main__":
    unittest.main()
