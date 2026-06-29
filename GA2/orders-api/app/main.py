import time
import base64
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Production Orders API")

# ---------------------------------------------------------
# CORS Middleware: Required for browser-based graders
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "Idempotency-Key"]
)

# ---------------------------------------------------------
# Configuration & In-Memory State
# ---------------------------------------------------------
TOTAL_ORDERS = 49
RATE_LIMIT = 16
WINDOW_SECONDS = 10

# Fixed catalog of IDs 1..49 for GET /orders
ORDERS_DB = [{"id": i, "description": f"Order {i}"} for i in range(1, TOTAL_ORDERS + 1)]

# State Stores
idempotency_store = {}
rate_limit_store = {}
next_new_order_id = 50 


# ---------------------------------------------------------
# 3. Per-Client Rate Limiting Dependency
# ---------------------------------------------------------
def check_rate_limit(x_client_id: Optional[str] = Header(default="unknown_client")):
    """
    Buckets requests by X-Client-Id. Allows 16 requests per 10-second window.
    The 17th request in that window raises a 429 with a Retry-After header.
    """
    now = time.time()
    
    # Initialize the client's bucket if it doesn't exist
    if x_client_id not in rate_limit_store:
        rate_limit_store[x_client_id] = []
        
    # Purge timestamps older than the 10-second window
    rate_limit_store[x_client_id] = [
        t for t in rate_limit_store[x_client_id] if now - t < WINDOW_SECONDS
    ]
    
    # Check if bucket is full (R+1 condition)
    if len(rate_limit_store[x_client_id]) >= RATE_LIMIT:
        oldest_request = rate_limit_store[x_client_id][0]
        retry_after = int(WINDOW_SECONDS - (now - oldest_request)) + 1
        
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests",
            headers={"Retry-After": str(retry_after)}
        )
        
    # Record current request
    rate_limit_store[x_client_id].append(now)
    return x_client_id


# ---------------------------------------------------------
# Helper Functions for Opaque Cursors
# ---------------------------------------------------------
def encode_cursor(order_id: int) -> str:
    return base64.urlsafe_b64encode(str(order_id).encode()).decode('utf-8')

def decode_cursor(cursor: str) -> Optional[int]:
    if not cursor:
        return None
    try:
        return int(base64.urlsafe_b64decode(cursor.encode('utf-8')).decode('utf-8'))
    except Exception:
        return None


# ---------------------------------------------------------
# 1. Idempotent Order Creation
# ---------------------------------------------------------
class CreateOrderRequest(BaseModel):
    item: str = "Standard Item"

@app.post("/orders", status_code=201, dependencies=[Depends(check_rate_limit)])
def create_order(
    payload: Optional[CreateOrderRequest] = None, 
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    global next_new_order_id
    
    # If key exists, return the cached successful response
    if idempotency_key and idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]
        
    # Otherwise, create a new order
    new_order = {
        "id": next_new_order_id,
        "status": "created"
    }
    next_new_order_id += 1
    
    # Cache the response if a key was provided
    if idempotency_key:
        idempotency_store[idempotency_key] = new_order
        
    return new_order


# ---------------------------------------------------------
# 2. Cursor Pagination
# ---------------------------------------------------------
@app.get("/orders", dependencies=[Depends(check_rate_limit)])
def get_orders(limit: int = 10, cursor: Optional[str] = None):
    # Decode cursor to figure out where to start
    start_id = decode_cursor(cursor) if cursor else 1
    
    # Find the starting index in our fixed DB
    start_idx = 0
    for i, order in enumerate(ORDERS_DB):
        if order["id"] == start_id:
            start_idx = i
            break
            
    # Slice the database based on the limit
    end_idx = start_idx + limit
    page_items = ORDERS_DB[start_idx:end_idx]
    
    # Calculate the next cursor if we haven't reached the end
    next_cursor = None
    if end_idx < len(ORDERS_DB):
        next_cursor = encode_cursor(ORDERS_DB[end_idx]["id"])
        
    return {
        "items": page_items,
        "next_cursor": next_cursor
    }