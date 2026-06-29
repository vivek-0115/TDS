from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import dotenv_values
import yaml
import os
from pathlib import Path

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

# Required: allow cross-origin from grader page
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Layer 1: defaults
DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000"
}


def parse_bool(v):
    return str(v).lower() in ["true", "1", "yes", "on"]


def coerce(key, value):
    if key in ["port", "workers"]:
        return int(value)
    elif key == "debug":
        return parse_bool(value)
    return str(value)

@app.get("/")
async def home():
    return {
        "message": "Config API is running"
    }

@app.get("/health")
async def health():
    return {
        "status": "ok"
    }

@app.get("/effective-config")
async def effective_config(set: list[str] = Query(default=[])):
    config = DEFAULTS.copy()

    # Layer 2: config.development.yaml
    with open(BASE_DIR / "config.development.yaml", "r") as f:
        yaml_config = yaml.safe_load(f) or {}
    for k, v in yaml_config.items():
        config[k] = coerce(k, v)

    # Layer 3: .env
    env_file = dotenv_values(BASE_DIR / ".env")

    # Alias NUM_WORKERS -> workers
    if "NUM_WORKERS" in env_file:
        env_file["workers"] = env_file.pop("NUM_WORKERS")

    for k, v in env_file.items():
        if k.startswith("APP_"):
            config[k[4:].lower()] = coerce(k[4:].lower(), v)

    # Layer 4: OS env (highest before CLI)
    for k, v in os.environ.items():
        if k.startswith("APP_"):
            config[k[4:].lower()] = coerce(k[4:].lower(), v)

    # CLI overrides (highest)
    for item in set:
        if "=" in item:
            key, value = item.split("=", 1)
            config[key] = coerce(key, value)

    # Secret masking
    config["api_key"] = "****"

    return config