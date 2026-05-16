from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import numpy as np

app = FastAPI(title="Latency API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load telemetry
with open("telemetry.json", "r") as f:
    telemetry = json.load(f)

# Request model
class RequestData(BaseModel):
    regions: list[str]
    threshold_ms: int

# Home route
@app.get("/")
def home():
    return {
        "message": "Latency Monitoring API is running"
    }

# Health route
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

# Main API
@app.post("/api/latency")
def latency(data: RequestData):

    result = {}

    for region in data.regions:

        records = [
            r for r in telemetry
            if r["region"] == region
        ]

        latencies = [r["latency_ms"] for r in records]
        uptimes = [r["uptime"] for r in records]

        result[region] = {
            "avg_latency": round(float(np.mean(latencies)), 2),
            "p95_latency": round(float(np.percentile(latencies, 95)), 2),
            "avg_uptime": round(float(np.mean(uptimes)), 4),
            "breaches": sum(
                1 for x in latencies
                if x > data.threshold_ms
            )
        }

    return result