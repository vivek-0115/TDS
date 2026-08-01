"""End-to-end local tests for the rebuilt FastAPI bot (webhook -> agent ->
shape enforcement -> Telegram reply). The agent and Telegram/GitHub calls are
mocked; everything else runs through the real FastAPI app."""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

# Dummy env values so the module imports without real secrets (all network
# calls below are mocked).
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-FAKE")
os.environ.setdefault("OPENAI_API_KEY", "test-fake")
os.environ.setdefault("OPENAI_BASE_URL", "https://aipipe.org/openai/v1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import api.index as bot  # noqa: E402

LOG_URL = "https://raw.githubusercontent.com/vivek-0115/TDS/main/run.jsonl"


class FakeAgent:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def run(self, messages):
        self.calls.append(list(messages))
        return self.outputs.pop(0)


def make_update(text, chat_id=12345, message_id=1):
    return {
        "update_id": 1,
        "message": {
            "message_id": message_id,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": 999, "is_bot": False, "first_name": "tester"},
            "text": text,
        },
    }


def post_update(payload, secret="secret123"):
    headers = {}
    if secret:
        headers["x-telegram-bot-api-secret-token"] = secret
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=bot.app), headers=headers
    ).post("http://testserver/webhook", json=payload)


async def run_case(name, payload, agent_answer, check, secret="secret123"):
    agent = FakeAgent([agent_answer])
    bot.get_agent = lambda: agent
    bot.chat_history.clear()
    bot.pending_log_lines.clear()
    sent = []
    bot.send_message = lambda cid, text: sent.append((cid, text))
    bot.push_log = lambda: None

    resp = await post_update(payload, secret)
    assert resp.status_code == 200, f"[{name}] status {resp.status_code}"

    reply = sent[-1][1] if sent else None
    assert reply is not None, f"[{name}] no reply sent"
    parsed = json.loads(reply)
    assert isinstance(parsed, dict), f"[{name}] reply is not a JSON object"
    check(name, parsed, reply)
    assert len(bot.pending_log_lines) >= 2, f"[{name}] run log not written"
    types = [json.loads(l)["type"] for l in bot.pending_log_lines]
    assert "incoming" in types and "outgoing" in types
    print(f"PASS: {name}")
    return agent


def main():
    bot.GITHUB_REPO = "vivek-0115/TDS"
    bot.GITHUB_TOKEN = "ghp_test"
    bot.LOG_URL = LOG_URL
    bot.WEBHOOK_SECRET = "secret123"

    q1 = 'What is 15% of 200? Reply with ONLY this JSON: {"answer": , "log_url": "..."}'

    # 1) Agent returns extra key + wrong log_url -> only requested keys remain.
    def check_answer_log(name, parsed, reply):
        assert set(parsed.keys()) == {"answer", "log_url"}, (
            f"[{name}] keys {list(parsed)} != [answer, log_url]"
        )
        assert parsed["answer"] == 30, f"[{name}] answer {parsed['answer']}"
        assert parsed["log_url"] == LOG_URL, f"[{name}] log_url {parsed['log_url']}"

    asyncio.run(run_case(
        "extra key + wrong log_url fixed",
        make_update(q1),
        {"answer": 30, "log_url": "http://wrong", "confidence": 0.99},
        check_answer_log,
    ))

    # 2) Shape with NO log_url (e.g. {"state": ...}) -> no log_url added.
    q2 = ('Which state has the highest maternal mortality rate based on MOSPI data? '
          'Reply with ONLY a JSON object like {"state": "<state name>"}')

    def check_state(name, parsed, reply):
        assert set(parsed.keys()) == {"state"}, (
            f"[{name}] keys {list(parsed)} != [state] (log_url must NOT be added)"
        )
        assert parsed["state"] == "Madhya Pradesh", f"[{name}] state {parsed['state']}"

    asyncio.run(run_case(
        "shape without log_url respected",
        make_update(q2),
        {"state": "Madhya Pradesh"},
        check_state,
    ))

    # 2b) Model wraps as {"answer": X} for a {"state": ...} shape -> unwrapped.
    def check_unwrapped(name, parsed, reply):
        assert set(parsed.keys()) == {"state"}, f"[{name}] keys {list(parsed)}"
        assert parsed["state"] == "Rajasthan", f"[{name}] state {parsed['state']}"

    asyncio.run(run_case(
        "answer-wrapped value unwrapped for single-key shape",
        make_update(q2),
        {"answer": "Rajasthan"},
        check_unwrapped,
    ))

    # 3) Missing requested key -> filled with null, shape intact.
    def check_missing(name, parsed, reply):
        assert set(parsed.keys()) == {"answer", "log_url"}, (
            f"[{name}] keys {list(parsed)} != [answer, log_url]"
        )
        assert parsed["answer"] is None, f"[{name}] answer should be null"
        assert parsed["log_url"] == LOG_URL, f"[{name}] log_url {parsed['log_url']}"

    asyncio.run(run_case(
        "missing key filled",
        make_update(q1),
        {"log_url": "x"},
        check_missing,
    ))

    # 3b) Plain value submitted (not wrapped in a dict) -> still shaped correctly.
    asyncio.run(run_case(
        "plain value wrapped into shape",
        make_update(q1),
        30,
        check_answer_log,
    ))

    # 4) No shape in message -> default answer/log_url contract.
    def check_default(name, parsed, reply):
        assert set(parsed.keys()) == {"answer", "log_url"}
        assert parsed["answer"] == 4
        assert parsed["log_url"] == LOG_URL

    asyncio.run(run_case(
        "no shape -> default contract",
        make_update("What is 2+2?"),
        {"answer": 4},
        check_default,
    ))

    # 5) Multi-turn: history survives across messages; answer targets last msg.
    async def multi_turn():
        bot.get_agent = lambda: FakeAgent([{"answer": 5}])
        bot.chat_history.clear()
        bot.pending_log_lines.clear()
        bot.send_message = lambda cid, text: None
        bot.push_log = lambda: None
        await post_update(make_update(
            "First: 10% of 50? Reply with ONLY this JSON: {\"answer\": , \"log_url\": \"...\"}"
        ))

        agent2 = FakeAgent([{"answer": 10}])
        bot.get_agent = lambda: agent2
        bot.pending_log_lines.clear()
        await post_update(make_update(
            "Now 20% of 50? Reply with ONLY this JSON: {\"answer\": , \"log_url\": \"...\"}"
        ))

        msgs = agent2.calls[-1]
        assert msgs[-1]["role"] == "user" and msgs[-1]["content"].startswith("Now 20%"), (
            f"last message not answered: {msgs[-1]}"
        )
        assert any(m["role"] == "assistant" for m in msgs), "earlier reply not in context"
        assert any(m["role"] == "user" and m["content"].startswith("First:") for m in msgs), (
            "earlier question not in context"
        )

    asyncio.run(multi_turn())
    print("PASS: multi-turn history fed to agent (last message answered)")

    # 6) Wrong webhook secret -> 401.
    async def bad_secret():
        resp = await post_update(make_update(q1), secret="wrong")
        assert resp.status_code == 401, f"secret status {resp.status_code}"
        print("PASS: wrong secret rejected")

    asyncio.run(bad_secret())

    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
