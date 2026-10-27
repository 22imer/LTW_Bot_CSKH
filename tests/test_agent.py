import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from cskh.agent import AgentError, build_system_prompt, run_agent
from cskh.db import Database
from cskh.knowledge import KnowledgeBase
from cskh.tools import ToolContext, execute_tool

STORES = {"s1": {"name": "N", "address": "A", "phone": "+84900000000", "hours": "8-9"}}


def tool_call(call_id, name, args):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def msg(content=None, tool_calls=None):
    data = {"role": "assistant", "content": content}
    if tool_calls:
        data["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in tool_calls]
    return SimpleNamespace(content=content, tool_calls=tool_calls, model_dump=lambda exclude_none=True: data)


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append({"tools": "tools" in kwargs, "messages": list(kwargs["messages"])})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return SimpleNamespace(choices=[SimpleNamespace(message=step)])


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.sqlite3")
        await self.db.open()
        await self.db.upsert_user(1, "A", None)
        self.sent = []

        async def send_contact(store_id):
            self.sent.append(store_id)

        kb = KnowledgeBase.from_texts(
            "Thanh toán\n- Thanh toán tại quầy.\n- Quán chưa có chuyển khoản tự động.\n",
            "## Cà phê\n- Cappuccino (M 48.000đ): Espresso, sữa nóng.\n",
        )
        self.ctx = ToolContext(1, STORES, self.db, kb, send_contact)

    async def asyncTearDown(self):
        await self.db.close()
        self.tmp.cleanup()

    async def run_agent(self, llm, history=()):
        return await run_agent(
            llm, "m", list(history), "hi", self.ctx,
            system_prompt="SYS", max_tool_rounds=3, timeout=5,
        )

    async def test_tool_results_feed_back_and_contact_is_sent(self):
        llm = FakeLLM([
            msg(tool_calls=[tool_call("c1", "get_store_contact", {"store_id": "s1"})]),
            msg("Đã gửi"),
        ])
        self.assertEqual(await self.run_agent(llm), "Đã gửi")
        self.assertEqual(self.sent, ["s1"])
        tool_msg = llm.calls[1]["messages"][-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(tool_msg["tool_call_id"], "c1")

    async def test_invalid_store_id_does_not_send_contact(self):
        llm = FakeLLM([
            msg(tool_calls=[tool_call("c1", "get_store_contact", {"store_id": "nope"})]),
            msg("Không có"),
        ])
        await self.run_agent(llm)
        self.assertEqual(self.sent, [])
        self.assertIn("error", json.loads(llm.calls[1]["messages"][-1]["content"]))

    async def test_feedback_tool_persists(self):
        llm = FakeLLM([
            msg(tool_calls=[tool_call("c1", "submit_feedback", {"category": "complaint", "content": "chậm"})]),
            msg("Đã ghi nhận"),
        ])
        await self.run_agent(llm)
        async with self.db.conn.execute("SELECT category, content FROM feedback") as cur:
            self.assertEqual(await cur.fetchall(), [("complaint", "chậm")])

    async def test_tool_rounds_are_capped_then_forced_to_text(self):
        looping = [msg(tool_calls=[tool_call(f"c{i}", "list_stores", {})]) for i in range(3)]
        llm = FakeLLM([*looping, msg("xong")])
        self.assertEqual(await self.run_agent(llm), "xong")
        self.assertEqual([c["tools"] for c in llm.calls], [True, True, True, False])

    async def test_search_knowledge_returns_matching_chunks_and_handles_no_match(self):
        found = json.loads(await execute_tool("search_knowledge", json.dumps({"query": "cappuccino gia"}), self.ctx))
        self.assertEqual([r["source"] for r in found["results"]], ["menu"])
        self.assertIn("48.000đ", found["results"][0]["text"])
        empty = json.loads(await execute_tool("search_knowledge", json.dumps({"query": "xyz"}), self.ctx))
        self.assertEqual(empty["results"], [])

    def test_system_prompt_names_the_shop_and_the_retrieval_tool(self):
        prompt = build_system_prompt("Mây Cafe")
        self.assertIn("Mây Cafe", prompt)
        self.assertIn("search_knowledge", prompt)

    async def test_system_prompt_is_sent_first(self):
        llm = FakeLLM([msg("ok")])
        await self.run_agent(llm)
        self.assertEqual(llm.calls[0]["messages"][0], {"role": "system", "content": "SYS"})

    async def test_history_is_sent_between_system_and_user(self):
        llm = FakeLLM([msg("ok")])
        await self.run_agent(llm, history=[{"role": "user", "content": "trước"}])
        roles = [m["role"] for m in llm.calls[0]["messages"]]
        self.assertEqual(roles, ["system", "user", "user"])

    async def test_llm_failure_and_empty_reply_raise_agent_error(self):
        for step in (RuntimeError("boom"), msg("   ")):
            with self.subTest(step=repr(step)), self.assertRaises(AgentError):
                await self.run_agent(FakeLLM([step]))


if __name__ == "__main__":
    unittest.main()
