from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import uuid
import time
from collections import deque

app = FastAPI()

EMAIL = "23f2004724@ds.study.iitm.ac.in"

# Startup time
START_TIME = time.time()

# In-memory log store
LOGS = deque(maxlen=1000)

# Prometheus counter
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests"
)


@app.middleware("http")
async def request_logger(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # increment counter for ALL requests
    HTTP_REQUESTS.inc()

    response = await call_next(request)

    # structured log
    LOGS.append({
        "level": "INFO",
        "ts": time.time(),
        "path": request.url.path,
        "request_id": request_id
    })

    return response


@app.get("/")
async def home():
    return {"message": "Observable API running"}


@app.get("/work")
async def work(n: int = Query(...)):
    # Simulate work
    for _ in range(n):
        pass

    return {
        "email": EMAIL,
        "done": n
    }


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(
        generate_latest().decode(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/healthz")
async def healthz():
    uptime = time.time() - START_TIME
    return {
        "status": "ok",
        "uptime_s": uptime
    }


@app.get("/logs/tail")
async def logs_tail(limit: int = 10):
    return list(LOGS)[-limit:]