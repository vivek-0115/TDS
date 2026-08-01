# TDS Project 1 - Data Analyst Telegram Bot

An LLM-powered Telegram bot that answers data-analysis questions. Receives a plain-text question via webhook, analyzes it using GPT-4o (via AIPipe) with tools (`fetch_url`, `python_repl`), and replies with a single JSON object matching **exactly** the shape the question asked for.

## Quick Start

1. **Clone and install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Fill in `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` (AIPipe key). For the public run log set `GITHUB_REPO` and `GITHUB_TOKEN` (fine-grained PAT with Contents: Read/Write); the bot pushes `run.jsonl` to the repo and `log_url` is its public raw GitHub link.

3. **Run locally**
   ```bash
   uvicorn api.index:app --port 8080
   ```

4. **Test locally** (agent, Telegram and GitHub calls mocked):
   ```bash
   python tests/test_local.py
   ```

5. **Set the Telegram webhook** (uses `WEBHOOK_SECRET` from `.env` automatically):
   ```bash
   python set_webhook.py https://your-deployed-url/webhook
   ```

## Deploy (Vercel)

```bash
vercel --prod
```

Set these environment variables in the Vercel project:
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` = `https://aipipe.org/openai/v1`
- `OPENAI_MODEL` = `gpt-4o`
- `GITHUB_REPO` = `owner/repo` (public repo hosting `run.jsonl`)
- `GITHUB_TOKEN` = PAT with Contents: Read/Write on that repo
- `WEBHOOK_SECRET` = random string (must match the one used by `set_webhook.py`)

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Telegram bot webhook (verifies `X-Telegram-Bot-Api-Secret-Token`) |
| `/test` | POST | Debug endpoint: returns the reply without sending to Telegram |
| `/health` | GET | Health check |

## How it Works

1. Telegram sends the question via webhook
2. The bot keeps per-chat context and always answers the **last** message
3. The agent analyzes the data (fetches URLs, runs Python via `python_repl`)
4. The agent submits the answer via the `submit_answer` tool
5. The bot enforces the exact JSON shape the question asked for (drops extra keys, fills missing ones, only adds `log_url` if the question asked for it)
6. The exchange is appended to the public `run.jsonl` log
