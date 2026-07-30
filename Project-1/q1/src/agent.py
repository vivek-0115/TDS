import io
import json
import re
import urllib.request

import pandas as pd
from openai import OpenAI

from src.logger import log_entry


SYSTEM_PROMPT = """You are a data analyst AI assistant. Your job is to answer data-analysis questions.

You have access to these tools:
1. fetch_url(url: str) -> str — Fetch content from a URL (CSV, JSON, HTML tables, etc.)
2. python_repl(code: str) -> str — Execute Python code for data analysis (pandas, numpy available as pd, np)

Rules:
- When you need data, first try fetching from URLs mentioned in the question.
- For inline data (data embedded in the question text), parse and analyze it directly.
- Use pandas for data analysis tasks.
- For MOSPI data, the URL is usually https://www.mospi.gov.in or similar — fetch and parse the relevant data.
- Once you have the answer, call the submit_answer tool with the final JSON object."""


SUBMIT_SCHEMA = {
    "name": "submit_answer",
    "description": "Submit the final answer as a JSON object with 'answer' and 'log_url' keys",
    "parameters": {
        "type": "object",
        "properties": {
            "answer": {
                "type": "object",
                "description": "The answer object matching the shape requested in the question",
            },
            "log_url": {
                "type": "string",
                "description": "URL to the JSONL log file",
            },
        },
        "required": ["answer", "log_url"],
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
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"}
                },
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
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
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

    def run(self, question: str, log_url: str) -> dict:
        log_entry("user", question)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        for step in range(25):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1,
            )

            msg = response.choices[0].message

            if not msg.tool_calls:
                content = msg.content or ""
                log_entry("assistant", content)
                fallback = self._try_extract_json(content, log_url)
                if fallback:
                    return fallback
                if step >= 23:
                    return {"answer": content[:200], "log_url": log_url}
                messages.append({"role": "assistant", "content": content})
                continue

            messages.append(msg)

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                args = json.loads(tc.function.arguments)
                log_entry("tool_call", f"{fn_name}({json.dumps(args)})", meta={"tool": fn_name, "args": args})

                if fn_name == "submit_answer":
                    args["log_url"] = log_url
                    return args

                result = TOOL_IMPL[fn_name](**args)
                log_entry("tool_result", str(result)[:500], meta={"tool": fn_name})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)[:4000],
                })

        return {"answer": "Failed to process question", "log_url": log_url}

    def _try_extract_json(self, content: str, log_url: str) -> dict | None:
        m = re.search(r'\{\s*"answer"\s*:', content, re.DOTALL)
        if m:
            try:
                start = m.start()
                depth = 0
                for i in range(start, len(content)):
                    if content[i] == "{":
                        depth += 1
                    elif content[i] == "}":
                        depth -= 1
                        if depth == 0:
                            parsed = json.loads(content[start:i + 1])
                            if "answer" in parsed:
                                if "log_url" not in parsed:
                                    parsed["log_url"] = log_url
                                return parsed
            except (json.JSONDecodeError, IndexError):
                pass
        return None
