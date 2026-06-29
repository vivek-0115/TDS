import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn

# =====================================================
# Configuration
# =====================================================

EMAIL = "23f2004724@ds.study.iitm.ac.in"

ALLOWED_ORIGINS = [
    "https://app-5k0wwt.example.com",
    "https://exam.sanand.workers.dev",
]

RATE_LIMIT = 12
WINDOW_SECONDS = 10

app = FastAPI(
    title="Middleware API",
    version="1.0.0",
)

# =====================================================
# Middleware 1 - Request Context
# =====================================================

@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)

    # Echo request ID in response header
    response.headers["X-Request-ID"] = request_id

    return response


# =====================================================
# Middleware 2 - Rate Limiter
# =====================================================

request_store = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_id = request.headers.get("X-Client-Id", "anonymous")
        now = time.time()

        bucket = request_store[client_id]

        # Remove expired requests
        while bucket and now - bucket[0] >= WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )

        bucket.append(now)

        return await call_next(request)


# =====================================================
# Middleware Registration
# =====================================================

app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# =====================================================
# Routes
# =====================================================

@app.get("/")
async def home():
    return {"message": "Middleware API Running"}


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }


# =====================================================
# Run locally
# =====================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )