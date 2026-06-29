from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()

API_KEY = "ak_682q0nrrnaloaldz7hhl97wt"
EMAIL = "23f2004724@ds.study.iitm.ac.in"

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


class Event(BaseModel):
    user: str
    amount: float
    ts: int


class AnalyticsRequest(BaseModel):
    events: List[Event]


@app.get("/")
async def home():
    return {"message": "Analytics API running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analytics")
async def analytics(
    payload: AnalyticsRequest,
    x_api_key: str = Header(None)
):
    # Auth check
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    events = payload.events

    total_events = len(events)
    unique_users = len(set(event.user for event in events))

    revenue = 0
    user_totals = {}

    for event in events:
        if event.amount > 0:
            revenue += event.amount
            user_totals[event.user] = (
                user_totals.get(event.user, 0) + event.amount
            )

    top_user = max(user_totals, key=user_totals.get) if user_totals else None

    return {
        "email": EMAIL,
        "total_events": total_events,
        "unique_users": unique_users,
        "revenue": revenue,
        "top_user": top_user
    }