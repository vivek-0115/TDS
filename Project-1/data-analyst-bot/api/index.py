import asyncio
import base64
import json
import os
import threading
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request

from src.agent import Agent
from src.logger import RUN_LOG, log_entry

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip().strip("/")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
LOG_URL_BASE = os.getenv("LOG_URL_BASE", "").strip()

# Public URL of the run log, downloadable with plain wget (no login). Prefer the
# GitHub raw link (guide Step 5); LOG_URL_BASE is a fallback (e.g. GCS bucket).
if LOG_URL_BASE:
    LOG_URL = f"{LOG_URL_BASE.rstrip('/')}/run.jsonl"
elif GITHUB_REPO:
    LOG_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/run.jsonl"
else:
    LOG_URL = ""

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("TELEGRAM_BOT_TOKEN and OPENAI_API_KEY must be set")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

app = FastAPI(title="TDS Project 1 - Data Analyst Bot")

# Per-chat message history (serverless memory is best-effort; recent turns only).
chat_history: dict[int, list[dict]] = {}
pending_log_lines: list[str] = []
_log_lock = threading.Lock()

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
    except Exception:
        pass


# --------------------------------------------------------------------------
# Run log -> pushed to the public run.jsonl (GitHub Contents API)
# --------------------------------------------------------------------------
def log_event(event: dict):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    with _log_lock:
        pending_log_lines.append(json.dumps(event) + "\n")


def push_log():
    """Append buffered lines to run.jsonl in GITHUB_REPO so LOG_URL stays live."""
    if not (GITHUB_REPO and GITHUB_TOKEN):
        return
    with _log_lock:
        if not pending_log_lines:
            return
        lines = "".join(pending_log_lines)
        pending_log_lines.clear()

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/run.jsonl"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    for _ in range(3):
        try:
            existing = requests.get(api_url, headers=headers, timeout=30)
            if existing.status_code == 200:
                body = existing.json()
                content = base64.b64decode(body.get("content", "")).decode(
                    "utf-8", errors="replace"
                ) + lines
                sha = body.get("sha")
            elif existing.status_code == 404:
                content, sha = lines, None
            else:
                return
            result = requests.put(
                api_url,
                headers=headers,
                timeout=30,
                json={
                    "message": "append run log",
                    "content": base64.b64encode(content.encode()).decode(),
                    "sha": sha,
                },
            )
            if result.status_code in (200, 201):
                return
            if result.status_code == 409:
                continue  # concurrent write from another instance: retry
            return
        except Exception:
            break
    with _log_lock:
        pending_log_lines.insert(0, lines)


# --------------------------------------------------------------------------
# JSON-shape enforcement - the grader compares whole-object equality, so the
# reply must be EXACTLY the shape the last message asked for, nothing more.
# --------------------------------------------------------------------------
def extract_requested_keys(user_text: str):
    """Top-level key names of the JSON shape embedded in the user's message.

    The shape may be written loosely ({"answer": , "log_url": "..."}), so it is
    scanned char-by-char: keys are quoted names at brace depth 1 before a colon.
    """
    start, end = user_text.find("{"), user_text.rfind("}")
    if start == -1 or end <= start:
        return None
    keys, depth, in_string, escape, i = [], 0, False, False, start
    while i <= end:
        ch = user_text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            j = i + 1
            name = []
            while j <= end:
                c = user_text[j]
                if c == "\\":
                    name.append(user_text[j:j + 2])
                    j += 2
                    continue
                if c == '"':
                    break
                name.append(c)
                j += 1
            k = j + 1
            while k <= end and user_text[k] in " \t\r\n":
                k += 1
            if k <= end and user_text[k] == ":" and depth == 1:
                keys.append("".join(name))
            i = j + 1
        elif ch == "{":
            depth += 1
            i += 1
        elif ch == "}":
            depth -= 1
            i += 1
        else:
            i += 1
    return keys if keys else None


def enforce_shape(parsed, user_text: str) -> str:
    """Turn the agent's answer into the exact JSON the message requested."""
    requested = extract_requested_keys(user_text)
    if requested is not None:
        if not isinstance(parsed, dict):
            # Plain value (number/string/bool) submitted directly - put it under
            # the shape's first key (e.g. {"answer": 30}).
            parsed = {requested[0]: parsed} if requested else {}
        elif len(requested) == 1 and requested[0] != "answer" and "answer" in parsed:
            # Model wrapped the answer as {"answer": X} even though the shape
            # wants a different single key (e.g. {"state": ...}) - unwrap it.
            val = parsed.pop("answer")
            if isinstance(val, dict):
                parsed = {k: v for k, v in val.items() if k in requested}
            else:
                parsed[requested[0]] = val
        # Drop keys the question did not ask for (they break exact match).
        parsed = {k: v for k, v in parsed.items() if k in requested}
        # Fill in requested keys the agent omitted.
        for k in requested:
            parsed.setdefault(k, None)
        # Only add log_url when the question asks for it - never add extras.
        if "log_url" in requested:
            parsed["log_url"] = LOG_URL
    else:
        # No shape given: keep the original answer/log_url contract.
        if not isinstance(parsed, dict):
            parsed = {"answer": parsed}
        parsed["log_url"] = LOG_URL
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------
# Core logic
# --------------------------------------------------------------------------
def process_and_reply(chat_id: int, text: str):
    log_event({"type": "incoming", "chat_id": chat_id, "text": text})

    history = chat_history.setdefault(chat_id, [])
    history.append({"role": "user", "content": text})

    try:
        RUN_LOG.clear()
        log_entry("user", text)
        answer = get_agent().run(history[-8:])
        final_reply = enforce_shape(answer, text)
        log_entry("assistant", final_reply)
    except Exception as e:
        log_entry("error", str(e))
        final_reply = enforce_shape({"answer": None}, text)

    history.append({"role": "assistant", "content": final_reply})
    chat_history[chat_id] = history[-30:]

    log_event({"type": "outgoing", "chat_id": chat_id, "text": final_reply})
    for e in RUN_LOG:
        log_event({"type": "agent", "role": e["role"], "content": e["content"]})

    send_message(chat_id, final_reply)
    push_log()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "TDS Project 1 - Data Analyst Bot is running", "log_url": LOG_URL}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if WEBHOOK_SECRET and x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret token")
    try:
        body = await request.json()
    except Exception:
        return {"ok": False}

    msg = body.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id or not text:
        return {"ok": True}

    if text == "/start":
        send_message(
            chat_id,
            "Hi! I'm a data analyst bot. Send me a data-analysis question and "
            "I'll reply with the answer as JSON.",
        )
        return {"ok": True}

    # Agent + log push are blocking; run them in a worker thread so the event
    # loop stays free (Telegram will wait for the HTTP response).
    await asyncio.to_thread(process_and_reply, chat_id, text)
    return {"ok": True}


@app.post("/test")
async def test(request: Request):
    """Manual debug endpoint: returns what the bot would reply, without Telegram."""
    try:
        body = await request.json()
        text = body.get("question", body.get("text", ""))
        if not text:
            return {"error": "no question provided"}
        chat_id = -1
        RUN_LOG.clear()
        answer = get_agent().run([{"role": "user", "content": text}])
        return {"reply": json.loads(enforce_shape(answer, text))}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}
