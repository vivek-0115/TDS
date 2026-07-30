import json
import os
import threading
import tempfile
from collections import defaultdict

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from src.agent import Agent
from src.logger import log_entry, RUN_LOG, dump_log

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
LOG_URL_BASE = os.getenv("LOG_URL_BASE", "")

app = FastAPI(title="TDS Project 1 - Data Analyst Bot")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_run_id = 0
_run_lock = threading.Lock()
LOG_DIR = os.path.join(tempfile.gettempdir(), "bot_logs")
os.makedirs(LOG_DIR, exist_ok=True)

chat_contexts: dict[int, list] = defaultdict(list)

_agent = None
_agent_lock = threading.Lock()


def get_agent():
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = Agent(
                    api_key=OPENAI_API_KEY,
                    base_url=OPENAI_BASE_URL or None,
                    model=OPENAI_MODEL,
                )
    return _agent


def send_message(chat_id: int, text: str):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
        }, timeout=30)
    except Exception as e:
        print(f"sendMessage error: {e}")


def process_and_reply(chat_id: int, text: str, rid: int, log_url: str):
    RUN_LOG.clear()
    log_entry("system", f"Run {rid}: received message", meta={"chat_id": chat_id})

    ctx = chat_contexts[chat_id]
    ctx.append(text)

    try:
        full_question = "\n".join(ctx) if len(ctx) > 1 else text
        result = get_agent().run(full_question, log_url)

        reply = json.dumps(result, ensure_ascii=False)
        log_entry("system", f"Final reply: {reply}")

        send_message(chat_id, reply)
        ctx.clear()
    except Exception as e:
        err_obj = {"answer": f"Error: {str(e)}", "log_url": log_url}
        send_message(chat_id, json.dumps(err_obj, ensure_ascii=False))
        log_entry("system", f"Error: {str(e)}")
        ctx.clear()

    log_data = dump_log()
    try:
        with open(os.path.join(LOG_DIR, f"{rid}.jsonl"), "w") as f:
            f.write(log_data)
    except Exception as e:
        print(f"Log write error: {e}")


@app.post("/webhook")
async def webhook(request: Request):
    global _run_id
    body = await request.json()

    msg = body.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")

    if not chat_id or not text:
        return Response(status_code=200)

    with _run_lock:
        _run_id += 1
        rid = _run_id

    public_url = LOG_URL_BASE.rstrip("/")
    log_url = f"{public_url}/logs/{rid}.jsonl"

    t = threading.Thread(target=process_and_reply, args=(chat_id, text, rid, log_url), daemon=False)
    t.start()

    return Response(status_code=200)


@app.get("/logs/{run_id}.jsonl")
async def get_log(run_id: int):
    path = os.path.join(LOG_DIR, f"{run_id}.jsonl")
    if os.path.exists(path):
        with open(path) as f:
            return Response(content=f.read(), media_type="application/jsonl")
    return PlainTextResponse("Log not found", status_code=404)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/test")
async def test(request: Request):
    global _run_id
    try:
        body = await request.json()
        text = body.get("question", body.get("text", ""))
        if not text:
            return {"error": "no question provided"}
        with _run_lock:
            _run_id += 1
            rid = _run_id
        public_url = LOG_URL_BASE.rstrip("/")
        log_url = f"{public_url}/logs/{rid}.jsonl"
        RUN_LOG.clear()
        result = get_agent().run(text, log_url)
        return {"answer": result, "log_url": log_url}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


@app.get("/")
async def root():
    return {"message": "TDS Project 1 - Data Analyst Bot is running"}
