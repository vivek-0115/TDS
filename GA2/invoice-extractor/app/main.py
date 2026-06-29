import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI

# -------------------------------------------------------------------
# Load environment variables
# -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    raise RuntimeError("GOOGLE_API_KEY not found in .env file")

# -------------------------------------------------------------------
# FastAPI App
# -------------------------------------------------------------------

app = FastAPI(
    title="Invoice Extractor API",
    version="1.0.0"
)

# -------------------------------------------------------------------
# Request & Response Models
# -------------------------------------------------------------------

class ExtractRequest(BaseModel):
    text: str


class Invoice(BaseModel):
    vendor: str
    amount: float
    currency: str
    date: str


# -------------------------------------------------------------------
# Initialize Gemini
# -------------------------------------------------------------------

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    api_key=api_key,
)

structured_llm = llm.with_structured_output(Invoice)

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.get("/")
async def home():
    return {
        "message": "Invoice Extractor API is running!",
        "model": "gemini-2.5-flash"
    }


@app.get("/test-gemini")
async def test_gemini():
    """
    Simple endpoint to verify Gemini is working.
    """
    try:
        response = llm.invoke(
            "Reply ONLY with the text: API_OK"
        )

        return {
            "success": True,
            "model": "gemini-2.5-flash",
            "response": response.content
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini test failed: {str(e)}"
        )


@app.post("/extract", response_model=Invoice)
async def extract(req: ExtractRequest):
    """
    Extract invoice information from raw invoice text.
    """

    if not req.text.strip():
        raise HTTPException(
            status_code=422,
            detail="Input text cannot be empty."
        )

    prompt = f"""
You are an expert invoice information extraction system.

Extract the following fields:

- vendor
- amount (final payable amount only)
- currency (ISO 4217 code like USD, INR, EUR, GBP)
- date (YYYY-MM-DD)

Rules:
- Return only the final invoice total.
- Ignore taxes unless included in the total.
- Normalize the date to YYYY-MM-DD.
- Infer currency from the symbol if needed.
- If the vendor is missing, infer it from the invoice.

Invoice Text:

{req.text}
"""

    try:
        invoice = structured_llm.invoke(prompt)
        return invoice

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {str(e)}"
        )


# -------------------------------------------------------------------
# Run Locally
# -------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )