# TDS Project 1 - Data Analyst Telegram Bot

An LLM-powered Telegram bot that answers data-analysis questions. Receives a plain-text question, analyzes it using GPT-4o (via AIPipe), and replies with a single JSON object.

## Quick Start

1. **Clone and install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   ```
   Fill in your `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, and `LOG_URL_BASE`.

3. **Run locally**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8080
   ```

4. **Set the Telegram webhook**
   ```bash
   python set_webhook.py https://your-deployed-url/webhook
   ```

## Deploy

### Render
1. Push to GitHub
2. Create a new **Web Service** on Render, connect your repo
3. Set the **Start Command** to `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL` = `https://aipipe.org/openai/v1`
   - `OPENAI_MODEL` = `gpt-4o`
   - `LOG_URL_BASE` = `https://your-app.onrender.com`

### Docker
```bash
docker build -t tds-bot .
docker run -p 8080:8080 --env-file .env tds-bot
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Telegram bot webhook |
| `/logs/{id}.jsonl` | GET | Run log as JSONL |
| `/health` | GET | Health check |

## How it Works

1. Telegram sends the question via webhook
2. The bot passes it to an LLM agent with tools (fetch_url, python_repl)
3. The agent analyzes the data (fetches from URLs, runs Python code)
4. The agent submits the answer via `submit_answer` tool
5. The bot replies with `{"answer": ..., "log_url": "..."}`
6. Every interaction is logged as JSONL

## Test Locally

Clone the official test harness:
```bash
git clone https://github.com/Jivraj-18/tds-p1-t2-2026-telegram-bot
cd tds-p1-t2-2026-telegram-bot
pip install -r requirements.txt
python run.py --bot-token YOUR_TOKEN --bot-username YOUR_BOT_USERNAME
```
