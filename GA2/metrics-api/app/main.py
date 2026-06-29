from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time

EMAIL = "23f2004724@ds.study.iitm.ac.in"

app = FastAPI()

# Strict CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dash-xn4rv0.example.com"
    ],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# Middleware for request ID + process time
@app.middleware("http")
async def add_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.6f}"

    return response


@app.get("/stats")
async def get_stats(values: str = Query(...)):
    try:
        nums = [int(x.strip()) for x in values.split(",") if x.strip()]
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid integer list"}
        )

    if not nums:
        return JSONResponse(
            status_code=400,
            content={"error": "Empty values"}
        )

    total = sum(nums)
    count = len(nums)

    result = {
        "email": EMAIL,
        "count": count,
        "sum": total,
        "min": min(nums),
        "max": max(nums),
        "mean": round(total / count, 2)
    }

    return result