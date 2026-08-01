import io
import json
import re
import urllib.request

import pandas as pd
from openai import OpenAI

from src.logger import log_entry


SYSTEM_PROMPT = """You are a data analyst AI assistant working inside a Telegram bot.
The user's LAST message is the question to answer (earlier messages are context only).
The question normally ends with an exact JSON shape to reply with, e.g.
{"answer": ...} or {"state": "<state name>"}.

Rules:
- Reply with ONLY the JSON object the question asks for: exactly its keys and
  nesting, no extra keys, no explanation, no markdown.
- Do NOT add a "log_url" key unless the question's shape asks for it - the
  platform adds the public log URL itself.
- You have these tools:
  1. fetch_url(url) - fetch a URL (CSV, JSON, HTML table, etc.)
  2. python_repl(code) - run Python (pandas as pd, numpy as np); store the
     answer in a variable named `result`.
- For simple math/trivia questions, answer directly with submit_answer.
- For data questions: fetch/parse the data, compute the answer, then submit.
- If a data source is unreachable or data is missing, still answer from your
  general knowledge (a reasonable estimate is far better than giving up) -
  NEVER reply with explanations, error text, or a refusal; always submit the
  JSON the question asked for.
- When ready, call submit_answer with the complete JSON object matching the
  requested shape."""


SUBMIT_SCHEMA = {
    "name": "submit_answer",
    "description": "Submit the final answer: a JSON object matching exactly the shape the question requested",
    "parameters": {
        "type": "object",
        "properties": {
            "answer": {
                "description": "The complete JSON object (or plain value) matching the requested shape",
            },
        },
        "required": ["answer"],
        "additionalProperties": False,
    },
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch content from a URL. Returns text content.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "python_repl",
            "description": "Execute Python code for data analysis. pandas available as pd, numpy as np. Store result in variable named 'result'.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string", "description": "Python code to execute"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": SUBMIT_SCHEMA,
    },
]


def fetch_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type:
                data = json.loads(raw)
                return json.dumps(data, indent=2)
            if "csv" in content_type or url.endswith(".csv"):
                df = pd.read_csv(io.StringIO(raw.decode("utf-8")))
                return df.to_csv(index=False)
            return raw.decode("utf-8")
    except Exception as e:
        return f"Error fetching URL: {e}"


def python_repl(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        code = code.strip("`")
        if code.startswith("python"):
            code = code[6:]
    code = code.strip()
    try:
        local_scope = {"pd": pd, "np": __import__("numpy"), "result": None}
        exec(code, {"__builtins__": __import__("builtins").__dict__}, local_scope)
        if local_scope.get("result") is not None:
            val = local_scope["result"]
            if isinstance(val, pd.DataFrame):
                return val.to_csv(index=False)
            return str(val)
        return "Code executed successfully (no result variable set)."
    except Exception as e:
        return f"Error: {e}"


TOOL_IMPL = {"fetch_url": fetch_url, "python_repl": python_repl}


class Agent:
    def __init__(self, api_key: str, base_url: str | None = None, model: str = "gpt-4o"):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def run(self, messages: list[dict]) -> dict:
        """Answer the LAST message; earlier messages are context.

        Returns the answer JSON object (any shape). Raises on failure.
        """
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + list(messages)
        last_content = None

        for step in range(8):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
                temperature=0.1,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                content = msg.content or ""
                log_entry("assistant", content)
                if content == last_content:
                    raise ValueError("agent stalled without an answer")
                last_content = content

                fallback = self._try_extract_json(content)
                if fallback is not None:
                    return fallback
                if step >= 7:
                    raise ValueError("agent did not produce a JSON answer")
                msgs.append({"role": "assistant", "content": content})
                continue

            msgs.append(msg)
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                args = json.loads(tc.function.arguments)
                log_entry("tool_call", f"{fn_name}({json.dumps(args)})",
                          meta={"tool": fn_name, "args": args})
                if fn_name == "submit_answer":
                    return args.get("answer")
                result = TOOL_IMPL[fn_name](**args)
                log_entry("tool_result", str(result)[:500], meta={"tool": fn_name})
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)[:4000],
                })

        raise ValueError("agent step limit reached")

    @staticmethod
    def _try_extract_json(content: str) -> dict | None:
        """Pull the first balanced {...} object out of model prose, if any."""
        start = content.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(content)):
            ch = content[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None
