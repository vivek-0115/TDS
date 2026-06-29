from fastapi import FastAPI
import redis
import os

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = 6379

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


@app.post("/hit/{key}")
async def hit(key: str):
    count = r.incr(key)
    return {
        "key": key,
        "count": count
    }


@app.get("/count/{key}")
async def count(key: str):
    value = r.get(key)
    return {
        "key": key,
        "count": int(value) if value else 0
    }


@app.get("/healthz")
async def healthz():
    try:
        r.ping()
        return {
            "status": "ok",
            "redis": "up"
        }
    except:
        return {
            "status": "error",
            "redis": "down"
        }